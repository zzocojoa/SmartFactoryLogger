// Attach to exactly one existing C32 page. No launch, close, reload or focus changes.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {createHash}=require('node:crypto');
const {parseArguments}=require('./observe_image_presentation.cjs');
const {resolveImageOrigin}=require('./observe_operator_image.cjs');
const {observePresentationV2}=require('./presentation_v2.cjs');

async function main(argv) {
  const options=parseArguments(argv),output=options['--out'];
  if(options['--client-id']!=='PC_1') throw Error('The server entry point requires PC_1');
  const fd=fs.openSync(output,'wx');let browser;
  const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
  const result={schema:'sfl-presentation-run-v2',context:'FIELD_CONNECTION_NOT_VISUALLY_ATTESTED',
    scope:'BROWSER_PRESENTATION_COMPONENT_ONLY',client_id:'PC_1',observer_hostname:os.hostname(),
    run_id:options['--run-id'],page_url:options['--page-url'],started_utc:new Date().toISOString(),
    expected_build:options['--expected-build'],collector_sha256:sha(path.join(__dirname,'presentation_v2.cjs')),
    entry_sha256:sha(__filename),release_gate:'HOLD',promotion_allowed:false};
  try {
    const {chromium}=require('playwright');
    browser=await chromium.connectOverCDP(options['--cdp'],{noDefaults:true,timeout:10000});
    result.browser_version=browser.version();
    const pages=browser.contexts().flatMap(c=>c.pages()).filter(p=>p.url()===options['--page-url']);
    if(pages.length!==1) throw Error('Exactly one existing target page required');
    const page=pages[0],origin=resolveImageOrigin(page.url(),options['--image-origin']);
    async function identity() {
      const response=await page.request.get(origin+'/health',{timeout:5000,maxRedirects:0});
      try {
        if(response.status()!==200) throw Error('Health identity unavailable');
        const data=await response.json(),spot=data.spot_temperature;
        const binding={build:spot?.build_git_commit,logger:spot?.v2_4_operational?.logger_service_instance_id};
        if(data.running!==true||binding.build!==options['--expected-build']||typeof binding.logger!=='string'
          ||!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(binding.logger)) throw Error('Runtime identity mismatch');
        return binding;
      }finally{await response.dispose();}
    }
    result.before=await identity();
    result.observation=await observePresentationV2(page,{durationMs:Number(options['--duration-ms']),readinessMs:10000,
      runId:options['--run-id'],clientId:'PC_1',imageOrigin:options['--image-origin']});
    result.after=await identity();
    if(JSON.stringify(result.before)!==JSON.stringify(result.after)) throw Error('Runtime generation changed');
    const gaps=result.observation.summary.incomplete.filter(x=>
      !['not-field-context','independent-window-and-white-screen-evidence-required'].includes(x));
    result.status=gaps.length?'CAPTURE_INCOMPLETE':'CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE';
  }catch(e){result.status='CAPTURE_INCOMPLETE';result.error=e.message;}
  finally {
    if(browser) await browser.close().catch(e=>{result.disconnect_error=e.message;result.status='CAPTURE_INCOMPLETE';});
    result.ended_utc=new Date().toISOString();
    const bytes=Buffer.from(JSON.stringify(result,null,2)+'\n');
    try{fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
    console.log(JSON.stringify({result_path:output,sha256:createHash('sha256').update(bytes).digest('hex'),
      status:result.status,release_gate:'HOLD',promotion_allowed:false}));
    process.exitCode=result.status==='CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE'?0:1;
  }
}
module.exports={main};
if(require.main===module) main(process.argv.slice(2)).catch(e=>{console.error(e.message);process.exitCode=1;});
