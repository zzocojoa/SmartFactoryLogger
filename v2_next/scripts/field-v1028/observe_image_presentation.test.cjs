const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const net = require('node:net');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {execFile}=require('node:child_process');
const {promisify}=require('node:util');
const { chromium } = require('playwright');
const { observePresentation, correlatePresentation, parseArguments } = require('./observe_image_presentation.cjs');

test('presentation component joins actual paint/blob/HTTP and restores page attributes', {timeout: 15000}, async () => {
  let requests = 0;
  const server = http.createServer((req, res) => {
    if (req.url.startsWith('/api/spot/live_image.jpg')) {
      requests++;
      res.writeHead(200, {'Content-Type':'image/svg+xml', 'X-Spot-Image-At':String(Date.now()), 'Cache-Control':'no-store'});
      res.end(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="rgb(${requests*25},30,90)"/></svg>`);
    } else {
      res.writeHead(200, {'Content-Type':'text/html'});
      res.end(`<div style="position:relative;width:200px;height:100px"><img class="camera-image" elementtiming="original" width="200" height="100"><button style="position:absolute;left:0;top:0;width:30px;height:20px">F</button></div><script>
        const img=document.querySelector('img'); let count=0;
        async function next(){const r=await fetch('/api/spot/live_image.jpg?t='+Date.now());img.src=URL.createObjectURL(await r.blob());}
        img.onload=()=>{count++;if(count<6)setTimeout(next,150);};window.start=next;
      </script>`);
    }
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.evaluate(()=>{window.originalArrayBuffer=Response.prototype.arrayBuffer;window.originalBlob=Response.prototype.blob;});
    const operation = observePresentation(page,{durationMs:1800,runId:'fixture',context:'HEADLESS_FIXTURE'});
    await page.waitForFunction(() => Boolean(window.__sflImagePresentationV1));
    await page.evaluate(() => window.start());
    const result = await operation;
    assert.deepEqual(result.errors,[]);
    assert.equal(requests,6); // Observer generated no new image HTTP requests.
    assert.equal(result.responses.length,6);
    assert.equal(result.dom.loads.length,6);
    assert.equal(result.summary.samples.length,6,JSON.stringify({summary:result.summary,loads:result.dom.loads,paints:result.dom.paints,responses:result.responses}));
    assert.ok(result.summary.samples.every(s=>s.presentation_confirmed && s.fresh_frame_identity_confirmed));
    assert.ok(result.dom.states.filter(s=>s.image_present).every(s=>!s.dom_occluded), 'Native edge controls must not mark the image interior occluded');
    assert.equal(result.summary.status,'INCOMPLETE');
    assert.equal(result.summary.promotion_allowed,false);
    assert.ok(result.summary.incomplete.includes('not-field-context'));
    assert.ok(result.summary.incomplete.includes('independent-window-and-white-screen-evidence-required'));
    assert.equal(await page.locator('img').getAttribute('elementtiming'),'original');
    assert.equal(await page.evaluate(()=>Boolean(window.__sflImagePresentationV1)),false);
    assert.equal(await page.evaluate(()=>typeof window.__sflPresentationHash_fixture),'undefined');
    assert.equal(await page.evaluate(()=>Response.prototype.arrayBuffer===window.originalArrayBuffer&&Response.prototype.blob===window.originalBlob),true);
  } finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
});

test('an actual overlay over the image interior remains an occlusion', {timeout:10000}, async () => {
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.route('http://127.0.0.1:1/**', route=>route.fulfill({contentType:'text/html',body:'<div style="position:relative;width:200px;height:100px"><img class="camera-image" width="200" height="100"><div style="position:absolute;inset:0;background:white"></div></div>'}));
    await page.goto('http://127.0.0.1:1/');
    const result=await observePresentation(page,{durationMs:500,runId:'occluded',context:'HEADLESS_FIXTURE'});
    assert.deepEqual(result.errors,[]);
    assert.ok(result.dom.states.length>0);
    assert.ok(result.dom.states.every(s=>s.dom_occluded));
    assert.ok(result.summary.incomplete.includes('visibility-focus-or-dom-occlusion'));
  } finally {await browser.close();}
});

function rawFixture() {
  return { context:'FIELD_VISIBLE_PC', errors:[], responses:[{id:'1',sha256:'abc',status:200,captured_at:'123'}],
    dom:{stopped:true,overflow:false,window_end_ms:1000,states:[],
      loads:[{url:'blob:fixture',at:100,sha256:'abc'}],
      paints:[{url:'blob:fixture',loadTime:100,presentationTime:120,observed_at:125,visible:true,dom_occluded:false}]} };
}

test('load-only, cached duplicate identity, ambiguous content and missing evidence never pass', () => {
  const loadOnly=rawFixture(); delete loadOnly.dom.paints[0].presentationTime;
  assert.ok(correlatePresentation(loadOnly).incomplete.includes('presentation-time-unavailable'));
  const ambiguous=rawFixture(); ambiguous.responses.push({...ambiguous.responses[0],id:'2'});
  assert.ok(correlatePresentation(ambiguous).incomplete.includes('ambiguous-or-missing-response-presentation'));
  const duplicate=rawFixture(); duplicate.responses.push({id:'2',sha256:'def',status:200,captured_at:'123'});
  duplicate.dom.loads.push({url:'blob:2',at:200,sha256:'def'});
  duplicate.dom.paints.push({url:'blob:2',loadTime:200,presentationTime:220,observed_at:225,visible:true,dom_occluded:false});
  assert.ok(correlatePresentation(duplicate).incomplete.includes('source-frame-identity-unconfirmed'));
  assert.equal(correlatePresentation({context:'FIELD_VISIBLE_PC',errors:[],responses:[],dom:null}).status,'INCOMPLETE');
});

test('a display completed after cutoff is preserved separately from measured frames',()=>{
  const raw=rawFixture();
  raw.responses.push({id:'2',sha256:'def',status:200,captured_at:'124'});
  raw.dom.loads.push({url:'blob:tail',at:995,sha256:'def'});
  raw.dom.paints.push({url:'blob:tail',loadTime:995,presentationTime:1005,observed_at:1010,visible:true,dom_occluded:false});
  raw.dom.states.push({at:1001,visible:false,focused:false,dom_occluded:true,image_present:false});
  const result=correlatePresentation(raw);
  assert.equal(result.samples.length,1);assert.equal(result.tail_presentations.length,1);
  assert.equal(result.tail_presentations[0].presented_at_ms,1005);
  assert.ok(!result.incomplete.includes('visibility-focus-or-dom-occlusion'));
});

test('CLI attaches only to an existing page, binds runtime identity, and disconnects without closing it', {timeout:25000}, async () => {
  let frames=0, wrongBuild=false, healthReads=0;
  const build='cd46692ac9c551080c57d8168fa9ea5abd530206';
  const server=http.createServer((req,res)=>{
    if(req.url==='/health') {healthReads++;res.setHeader('content-type','application/json');res.end(JSON.stringify({spot_temperature:{build_git_commit:wrongBuild?'0'.repeat(40):build,v2_4_operational:{logger_service_instance_id:'11111111-2222-3333-4444-555555555555'}}}));return;}
    if(req.url.startsWith('/api/spot/live_image.jpg')) {
      frames++;res.writeHead(200,{'content-type':'image/svg+xml','X-Spot-Image-At':String(Date.now()),'cache-control':'no-store'});
      res.end(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><text x="20" y="50">${frames}</text></svg>`);return;
    }
    res.setHeader('content-type','text/html');res.end(`<img class="camera-image" width="200" height="100"><script>
      const img=document.querySelector('img');async function next(){const r=await fetch('/api/spot/live_image.jpg?t='+Date.now());img.src=URL.createObjectURL(await r.blob());}img.onload=()=>setTimeout(next,150);next();</script>`);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const reservation=net.createServer();await new Promise(resolve=>reservation.listen(0,'127.0.0.1',resolve));
  const port=reservation.address().port;await new Promise(resolve=>reservation.close(resolve));
  const browser=await chromium.launch({headless:true,args:[`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1']});
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'sfl-presentation-test-'));
  const output=path.join(directory,'capture.json'),rejected=path.join(directory,'rejected.json');
  try {
    const page=await browser.newPage(),url=`http://127.0.0.1:${server.address().port}/dashboard`;
    await page.goto(url);await page.waitForFunction(()=>document.querySelector('img').complete&&document.querySelector('img').naturalWidth>0);
    const args=['--cdp',`http://127.0.0.1:${port}`,'--page-url',url,'--client-id','fixture','--run-id','cli_fixture','--duration-ms','1000','--out',output,'--expected-build',build];
    assert.doesNotThrow(()=>parseArguments(args));
    assert.throws(()=>parseArguments([...args,'--run-id','again']),/repeated/);
    const remote=[...args];remote[1]='http://192.0.2.1:9222';assert.throws(()=>parseArguments(remote),/local CDP/);
    const long=[...args];long[9]='900001';assert.throws(()=>parseArguments(long),/Bounded/);
    const child=await promisify(execFile)(process.execPath,[path.join(__dirname,'observe_image_presentation.cjs'),...args],{timeout:15000});
    assert.equal(JSON.parse(child.stdout).status,'CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE');
    const result=JSON.parse(fs.readFileSync(output));
    assert.equal(result.before.build,build);assert.deepEqual(result.before,result.after);assert.equal(healthReads,2);
    assert.equal(result.promotion_allowed,false);assert.ok(result.observation.summary.samples.length>=3);
    assert.equal(browser.isConnected(),true);assert.equal(page.isClosed(),false);
    assert.equal(await page.evaluate(()=>Boolean(window.__sflImagePresentationV1)),false);
    assert.throws(()=>parseArguments(args),/New absolute output/);
    wrongBuild=true;const wrong=[...args];wrong[11]=rejected;
    await assert.rejects(promisify(execFile)(process.execPath,[path.join(__dirname,'observe_image_presentation.cjs'),...wrong],{timeout:15000}),error=>error.code===1);
    const rejectedResult=JSON.parse(fs.readFileSync(rejected));
    assert.match(rejectedResult.error,/identity mismatch/);assert.equal(rejectedResult.observation,undefined);
    assert.equal(page.isClosed(),false);assert.equal(await page.evaluate(()=>Boolean(window.__sflImagePresentationV1)),false);
  } finally {
    await browser.close();await new Promise(resolve=>server.close(resolve));
    for(const p of [output,rejected]) if(fs.existsSync(p)) fs.unlinkSync(p);
    fs.rmdirSync(directory);
  }
});
