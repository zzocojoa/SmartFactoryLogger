const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {waitForManualPresentationStart:wait}=require('./presentation_manual_start.cjs');
async function fixture(run) {
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.setContent('<div style="height:150px"></div><img class="camera-image" width="200" height="100">');
    await page.evaluate(()=>{window.originalFetch=fetch;window.originalFocus=document.hasFocus;});
    await run(page);
    assert.deepEqual(await page.evaluate(()=>({panel:!!document.querySelector('[data-sfl-presentation-manual-start]'),
      capture:!!window.__sflImagePresentationV2,fetchChanged:fetch!==originalFetch,focusChanged:document.hasFocus!==originalFocus})),
      {panel:false,capture:false,fetchChanged:false,focusChanged:false});
  }finally{await browser.close();}
}
test('manual preparation does not start automatically or from a synthetic click',async()=>{
  await fixture(async page=>{
    const pending=page.evaluate(wait,{clientId:'PC_2',timeoutMs:3000});
    await page.waitForSelector('[data-sfl-presentation-manual-start]');
    await page.getByRole('button',{name:'15분 측정 시작'}).evaluate(button=>button.click());
    assert.equal(await page.locator('[data-sfl-presentation-manual-start]').count(),1);
    await page.getByRole('button',{name:'15분 측정 시작'}).click();
    const result=await pending;
    assert.equal(result.status,'READY');
    assert.ok(result.states.some(s=>s.event_type==='click'&&!s.trusted));
    assert.ok(result.states.at(-1).trusted&&result.states.at(-1).focused);
  });
});
test('an actual button click cannot override missing focus',async()=>{
  await fixture(async page=>{
    await page.evaluate(()=>{document.hasFocus=()=>false;});
    const pending=page.evaluate(wait,{clientId:'PC_2',timeoutMs:3000});
    await page.getByRole('button',{name:'15분 측정 시작'}).click();
    assert.equal(await page.locator('[data-sfl-presentation-manual-start]').count(),1);
    await page.evaluate(()=>{document.hasFocus=originalFocus;});
    await page.getByRole('button',{name:'15분 측정 시작'}).click();
    const result=await pending;assert.equal(result.status,'READY');
    assert.ok(result.states.some(s=>s.trusted&&!s.focused));
  });
});
test('hidden state blocks a trusted click and cancellation cleans up',async()=>{
  await fixture(async page=>{
    await page.evaluate(()=>Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'hidden'}));
    const pending=page.evaluate(wait,{clientId:'PC_2',timeoutMs:3000});
    await page.getByRole('button',{name:'15분 측정 시작'}).click();
    assert.equal(await page.locator('[data-sfl-presentation-manual-start]').count(),1);
    await page.getByRole('button',{name:'취소',exact:true}).click();
    assert.equal((await pending).status,'CANCELLED');
  });
});
test('deadline records incomplete preparation without installing capture',async()=>{
  await fixture(async page=>{
    const result=await page.evaluate(wait,{clientId:'PC_2',timeoutMs:200});
    assert.equal(result.status,'NOT_READY');assert.ok(result.ended_ms-result.started_ms>=200);
    assert.ok(result.states.every(s=>s.event_type==='poll'));
  });
});
test('camera occlusion blocks start and cancellation remains available',async()=>{
  await fixture(async page=>{
    await page.evaluate(()=>{const d=document.createElement('div');d.style.cssText='position:absolute;left:8px;top:158px;width:200px;height:100px;background:white';document.body.append(d);});
    const pending=page.evaluate(wait,{clientId:'PC_2',timeoutMs:3000});
    await page.getByRole('button',{name:'15분 측정 시작'}).click();
    assert.equal(await page.locator('[data-sfl-presentation-manual-start]').count(),1);
    await page.getByRole('button',{name:'취소',exact:true}).click();
    const result=await pending;assert.equal(result.status,'CANCELLED');
    assert.ok(result.states.some(s=>s.trusted&&s.dom_occluded));
  });
});
test('no room outside image fails without covering the image',async()=>{
  await fixture(async page=>{
    await page.evaluate(()=>{document.querySelector('img').style.cssText='position:fixed;inset:0;width:100vw;height:100vh';});
    const result=await page.evaluate(wait,{clientId:'PC_2',timeoutMs:200});
    assert.equal(result.status,'NOT_READY');assert.match(result.error,/cannot fit outside camera/);
  });
});
