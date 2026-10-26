const {test} = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {chromium} = require('playwright');
const {observePresentationV2:observeBase, correlateV2, waitForPresentationReady} = require('./presentation_v2.cjs');
const observePresentationV2=(page,options)=>observeBase(page,{readinessMs:1000,...options});

async function fixture(run, mode = 'array', responseDelay = 0) {
  let requests = 0;
  const server = http.createServer((req,res) => {
    if(req.url.startsWith('/api/spot/live_image.jpg')) {
      requests++;
      res.writeHead(200, {'content-type':'image/svg+xml','X-Spot-Image-At':String(1000+requests),'cache-control':'no-store'});
      // Identical bytes deliberately; only actual response identity distinguishes them.
      setTimeout(()=>res.end('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="red"/></svg>'),responseDelay);
    } else {
      res.setHeader('content-type','text/html');
      res.end(`<div style="height:100px"></div><img class="camera-image" width="200" height="100" elementtiming="original"><script>
        let count=0; const img=document.querySelector('img');
        window.start=async()=>{const r=await fetch('/api/spot/live_image.jpg?t='+count);
          let blob;if('${mode}'==='blob')blob=await r.blob();else{
            const bytes=new Uint8Array(await r.arrayBuffer());
            blob=new Blob(['${mode}'==='copy'?bytes.slice():bytes],{type:'image/svg+xml'});
          } img.src=URL.createObjectURL(blob);};
        img.onload=()=>{if(++count<6)setTimeout(start,120);};
        window.originals={fetch,Blob,create:URL.createObjectURL,ab:Response.prototype.arrayBuffer,blob:Response.prototype.blob};
      </script>`);
    }
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}/dashboard`);
    await run(page,()=>requests);
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
}

test('repeated identical bytes keep exact ArrayBuffer/Blob/URL response lineage', {timeout:15000}, async()=>{
  await fixture(async(page,requests)=>{
    const pending=observePresentationV2(page,{durationMs:1500,runId:'same_bytes',clientId:'PC_2',context:'HEADLESS_FIXTURE'});
    await page.waitForFunction(()=>!!window.__sflImagePresentationV2);
    await page.evaluate(()=>start());
    const raw=await pending;
    assert.deepEqual(raw.errors,[]);
    assert.equal(requests(),6,'observer must not add image HTTP requests');
    assert.equal(raw.responses.length,6);
    assert.equal(new Set(raw.responses.map(r=>r.sha256)).size,1);
    assert.equal(raw.summary.samples.length,6,JSON.stringify(raw.summary.incomplete));
    assert.equal(new Set(raw.summary.samples.map(r=>r.response_id)).size,6);
    assert.equal(raw.summary.promotion_allowed,false);
    assert.deepEqual(await page.evaluate(()=>({
      fetch:fetch===originals.fetch,Blob:Blob===originals.Blob,url:URL.createObjectURL===originals.create,
      ab:Response.prototype.arrayBuffer===originals.ab,blob:Response.prototype.blob===originals.blob,
      observer:!window.__sflImagePresentationV2,attribute:document.querySelector('img').getAttribute('elementtiming')
    })),{fetch:true,Blob:true,url:true,ab:true,blob:true,observer:true,attribute:'original'});
  });
});

test('a request already in flight is retained before the fixed measurement boundary', {timeout:12000},async()=>{
  await fixture(async(page,requests)=>{
    await page.evaluate(()=>{void start();});
    while(requests()===0) await page.waitForTimeout(10);
    const raw=await observePresentationV2(page,{durationMs:1500,readinessMs:2000,runId:'inflight',clientId:'PC_2'});
    assert.equal(raw.dom.contract_revision,2);
    assert.ok(raw.dom.window_start_ms>raw.dom.installed_at_ms);
    assert.equal(raw.dom.window_end_ms-raw.dom.window_start_ms,1500);
    assert.ok(raw.dom.loads.some(x=>x.at<raw.dom.window_start_ms&&x.error==='response-blob-url-lineage-missing'));
    assert.ok(raw.summary.samples.length>=3);
    assert.ok(!raw.summary.incomplete.includes('response-blob-presentation-unbound'));
    assert.equal(raw.dom.boundary.response_id,raw.summary.samples[0].response_id);
    assert.equal(raw.dom.boundary.presentation_time_ms,raw.dom.window_start_ms);
  },'array',200);
});

test('native Response.blob lineage works; a byte copy is never guessed', {timeout:20000},async()=>{
  for(const mode of ['blob','copy']) await fixture(async page=>{
    const pending=observePresentationV2(page,{durationMs:1500,runId:mode,clientId:'PC_2',context:'HEADLESS_FIXTURE'});
    await page.waitForFunction(()=>!!window.__sflImagePresentationV2);await page.evaluate(()=>start());
    const raw=await pending;assert.deepEqual(raw.errors,[]);
    assert.equal(raw.summary.samples.length,mode==='blob'?6:0);
    if(mode==='copy') {
      assert.ok(raw.summary.incomplete.includes('measurement-boundary-missing'));
      assert.ok(raw.dom.loads.every(x=>x.error==='response-blob-url-lineage-missing'));
      assert.equal(raw.dom.stop_reason,'readiness-deadline');
    }
  },mode);
});

test('loading a new src is recorded separately from DOM visibility; true removal is retained', {timeout:10000},async()=>{
  await fixture(async page=>{
    await page.route('**/slow-image',async route=>{
      await new Promise(resolve=>setTimeout(resolve,300));
      await route.fulfill({contentType:'image/svg+xml',body:'invalid image'});
    });
    const pending=observePresentationV2(page,{durationMs:700,runId:'loading',clientId:'PC_2'});
    await page.waitForFunction(()=>!!window.__sflImagePresentationV2);
    await page.evaluate(()=>{const img=document.querySelector('img');img.src='/slow-image';});
    await page.waitForTimeout(400);
    await page.evaluate(()=>document.querySelector('img').remove());
    const raw=await pending;
    assert.ok(raw.dom.states.some(s=>s.dom_present&&!s.load_complete&&s.natural_width===0));
    assert.ok(raw.dom.states.some(s=>!s.dom_present));
    assert.ok(raw.summary.incomplete.includes('visibility-focus-or-dom-occlusion'));
    assert.ok(raw.dom.errors.includes('image-element-error'));
  });
});

test('unavailable camera, occupied observer and invalid duration leave native APIs intact', {timeout:10000},async()=>{
  for(const mode of ['missing','occupied','duration']) await fixture(async page=>{
    if(mode==='missing') await page.evaluate(()=>document.querySelector('img').remove());
    if(mode==='occupied') await page.evaluate(()=>window.__sflImagePresentationV1={sentinel:true});
    const raw=await observePresentationV2(page,{durationMs:mode==='duration'?900001:500,runId:mode,clientId:'PC_2'});
    assert.equal(raw.errors.length,1);assert.equal(raw.summary.status,'INCOMPLETE');
    assert.equal(await page.evaluate(()=>window.fetch===originals.fetch&&Blob===originals.Blob
      &&URL.createObjectURL===originals.create&&!window.__sflImagePresentationV2
      &&!Object.keys(window).some(k=>k.startsWith('__sflPresentationHashV2_'))),true);
    if(mode==='occupied') assert.equal(await page.evaluate(()=>window.__sflImagePresentationV1.sentinel),true);
  });
});

test('early stop restores hooks and reports incomplete; an external replacement is not overwritten', {timeout:10000},async()=>{
  await fixture(async page=>{
    const pending=observePresentationV2(page,{durationMs:500,runId:'early',clientId:'PC_2'});
    await page.waitForFunction(()=>!!window.__sflImagePresentationV2);
    const stopped=await page.evaluate(()=>{
      window.otherFetch=function(){throw Error('external');};window.fetch=otherFetch;
      const value=window.__sflImagePresentationV2.stop('test-stop');
      return {early:value.early_stop,ours:window.fetch===otherFetch,blob:Blob===originals.Blob,panel:!!document.querySelector('[data-sfl-presentation]')};
    });
    assert.deepEqual(stopped,{early:true,ours:true,blob:true,panel:false});
    const raw=await pending;
    assert.ok(raw.summary.incomplete.includes('collector-incomplete'));
    assert.ok(raw.dom.errors.includes('fetch observer replaced externally'));
  });
});

test('missing or altered lineage and duplicate backend receipt cannot become fresh frames', {timeout:10000},async()=>{
  await fixture(async page=>{
    const pending=observePresentationV2(page,{durationMs:1300,runId:'negative',clientId:'PC_2'});
    await page.waitForFunction(()=>!!window.__sflImagePresentationV2);await page.evaluate(()=>start());
    const raw=await pending;
    const cases=[
      [r=>delete r.dom.loads[0].response_id,'response-blob-presentation-unbound'],
      [r=>r.dom.loads[0].sha256='0'.repeat(64),'response-blob-bytes-mismatch'],
      [r=>r.responses[2].captured_at=r.responses[0].captured_at,'source-frame-identity-conflict'],
      [r=>delete r.dom.paints[0].presentationTime,'presentation-time-unavailable'],
      [r=>r.dom.states.find(s=>s.at>=r.dom.window_start_ms).visible=false,'visibility-focus-or-dom-occlusion'],
      [r=>r.dom.states.find(s=>s.at>=r.dom.window_start_ms).dom_occluded=true,'visibility-focus-or-dom-occlusion']
    ];
    for(const [mutate,reason] of cases){const changed=structuredClone(raw);mutate(changed);assert.ok(correlateV2(changed).incomplete.includes(reason),reason);}
    const loading=structuredClone(raw);
    loading.dom.states.forEach(s=>{s.load_complete=false;s.natural_width=0;});
    assert.ok(!correlateV2(loading).incomplete.includes('visibility-focus-or-dom-occlusion'));
    assert.equal(correlateV2(loading).actual_screen_and_white_screen_status,'NOT_EVALUATED');
    assert.ok(raw.summary.incomplete.includes('independent-window-and-white-screen-evidence-required'));
    const repeated=structuredClone(raw);
    repeated.responses[1].captured_at=repeated.responses[0].captured_at;
    const joined=correlateV2(repeated);
    assert.equal(joined.samples.length,5);assert.equal(joined.repeated_presentations.length,1);
    assert.equal(joined.repeated_presentations[0].fresh_frame_identity_confirmed,false);
    assert.ok(!joined.incomplete.some(x=>x.startsWith('source-frame')));
    repeated.responses[1].sha256='b'.repeat(64);repeated.dom.loads[1].sha256='b'.repeat(64);
    assert.ok(correlateV2(repeated).incomplete.includes('source-frame-identity-conflict'));
  });
});

test('preflight records unfocused visible page and waits without changing focus', {timeout:10000},async()=>{
  await fixture(async page=>{
    // Controlled fixture only; field code never overrides these APIs.
    await page.evaluate(()=>{window.realHasFocus=document.hasFocus;document.hasFocus=()=>false;});
    const pending=page.evaluate(waitForPresentationReady,{clientId:'PC_2',timeoutMs:2000});
    await page.waitForSelector('[data-sfl-presentation-preflight]');
    assert.match(await page.locator('[data-sfl-presentation-preflight]').innerText(),/아직 15분 측정은 시작되지 않았습니다/);
    assert.equal(await page.evaluate(()=>document.hasFocus()),false);
    await page.evaluate(()=>{document.hasFocus=realHasFocus;});
    const result=await pending;
    assert.equal(result.status,'READY');assert.ok(result.states.some(s=>s.visible&&!s.focused));
    assert.equal(await page.locator('[data-sfl-presentation-preflight]').count(),0);
    assert.equal(await page.evaluate(()=>fetch===originals.fetch&&!window.__sflImagePresentationV2),true);
  });
});

test('preflight deadline retains focus/visibility separately and never starts capture', {timeout:10000},async()=>{
  await fixture(async page=>{
    await page.evaluate(()=>{document.hasFocus=()=>false;});
    const result=await page.evaluate(waitForPresentationReady,{clientId:'PC_2',timeoutMs:200});
    assert.equal(result.status,'NOT_READY');assert.ok(result.states.every(s=>s.visible&&!s.focused));
    assert.ok(result.ended_ms-result.started_ms>=200);
    assert.equal(await page.locator('[data-sfl-presentation-preflight]').count(),0);
    assert.equal(await page.evaluate(()=>fetch===originals.fetch&&!window.__sflImagePresentationV2),true);
  });
});

test('status banner reports focus loss without changing focus and stays outside image', {timeout:10000},async()=>{
  await fixture(async page=>{
    const pending=observePresentationV2(page,{durationMs:700,runId:'banner',clientId:'PC_2'});
    await page.waitForFunction(()=>!!window.__sflImagePresentationV2);
    const result=await page.evaluate(()=>{
      const panel=document.querySelector('[data-sfl-presentation]'),p=panel.getBoundingClientRect(),i=document.querySelector('img').getBoundingClientRect();
      // Test the warning path. Real field visibility is never overridden.
      const original=document.hasFocus;document.hasFocus=()=>false;window.dispatchEvent(new Event('blur'));
      const warning=panel.textContent;document.hasFocus=original;
      return {warning,overlap:!(p.right<=i.left||p.left>=i.right||p.bottom<=i.top||p.top>=i.bottom),
        fits:panel.scrollWidth<=panel.clientWidth&&panel.scrollHeight<=panel.clientHeight};
    });
    assert.match(result.warning,/PC_2.*화면 연결 준비/s);assert.match(result.warning,/주의/);assert.equal(result.overlap,false);
    assert.equal(result.fits,true,'status text must stay within the measured panel bounds');
    const raw=await pending;assert.ok(raw.summary.incomplete.includes('visibility-focus-or-dom-occlusion'));
  });
});
