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
const { parseArguments } = require('./observe_image_presentation.cjs');

test('v2 CLI attaches only to an existing page, binds runtime identity, and disconnects without closing it', {timeout:25000}, async () => {
  let frames=0, wrongBuild=false, healthReads=0;
  const build='cd46692ac9c551080c57d8168fa9ea5abd530206';
  const server=http.createServer((req,res)=>{
    if(req.url==='/health') {healthReads++;res.setHeader('content-type','application/json');res.end(JSON.stringify({running:true,spot_temperature:{build_git_commit:wrongBuild?'0'.repeat(40):build,v2_4_operational:{logger_service_instance_id:'11111111-2222-3333-4444-555555555555'}}}));return;}
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
    const args=['--cdp',`http://127.0.0.1:${port}`,'--page-url',url,'--client-id','PC_1','--run-id','cli_fixture','--duration-ms','1000','--out',output,'--expected-build',build];
    assert.doesNotThrow(()=>parseArguments(args));
    assert.throws(()=>parseArguments([...args,'--run-id','again']),/repeated/);
    const remote=[...args];remote[1]='http://192.0.2.1:9222';assert.throws(()=>parseArguments(remote),/local CDP/);
    const long=[...args];long[9]='900001';assert.throws(()=>parseArguments(long),/Bounded/);
    const child=await promisify(execFile)(process.execPath,[path.join(__dirname,'observe_presentation_v2.cjs'),...args],{timeout:15000});
    assert.equal(JSON.parse(child.stdout).status,'CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE');
    const result=JSON.parse(fs.readFileSync(output));
    assert.equal(result.before.build,build);assert.deepEqual(result.before,result.after);assert.equal(healthReads,2);
    assert.equal(result.promotion_allowed,false);assert.ok(result.observation.summary.samples.length>=3);
    assert.equal(browser.isConnected(),true);assert.equal(page.isClosed(),false);
    assert.equal(await page.evaluate(()=>Boolean(window.__sflImagePresentationV2)),false);
    assert.throws(()=>parseArguments(args),/New absolute output/);
    wrongBuild=true;const wrong=[...args];wrong[11]=rejected;
    await assert.rejects(promisify(execFile)(process.execPath,[path.join(__dirname,'observe_presentation_v2.cjs'),...wrong],{timeout:15000}),error=>error.code===1);
    const rejectedResult=JSON.parse(fs.readFileSync(rejected));
    assert.match(rejectedResult.error,/identity mismatch/);assert.equal(rejectedResult.observation,undefined);
    assert.equal(page.isClosed(),false);assert.equal(await page.evaluate(()=>Boolean(window.__sflImagePresentationV2)),false);
  } finally {
    await browser.close();await new Promise(resolve=>server.close(resolve));
    for(const p of [output,rejected]) if(fs.existsSync(p)) fs.unlinkSync(p);
    fs.rmdirSync(directory);
  }
});
