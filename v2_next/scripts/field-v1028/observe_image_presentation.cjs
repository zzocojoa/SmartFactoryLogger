// Read actual browser presentation events; never manufacture an operational PASS.
// This collector does not open/close pages, replace timers, or issue device requests.
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { resolveImageOrigin } = require('./observe_operator_image.cjs');
const KEY = '__sflImagePresentationV1';
const MAX_EVENTS = 12000;

async function bounded(promise, milliseconds) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => {
    timer=setTimeout(()=>reject(new Error('Observer operation deadline')),milliseconds);
  })]); } finally { clearTimeout(timer); }
}

function correlatePresentation(raw) {
  const incomplete = [...raw.errors];
  if (!raw.dom || raw.dom.overflow || !raw.dom.stopped) incomplete.push('collector-incomplete');
  const samples = [], tailPresentations = [], identities = new Set();
  const loads = raw.dom?.loads ?? [], paints = raw.dom?.paints ?? [];
  const inWindowLoads = loads.filter(e => e.at <= raw.dom.window_end_ms);
  for (const load of inWindowLoads) {
    if (!load.sha256 || load.error) { incomplete.push('blob-read-incomplete'); continue; }
    // Reject ambiguous content matches, including repeated identical response bodies.
    // Response delivery order alone does not establish exact frame attribution.
    const responses = raw.responses.filter(r => r.sha256 === load.sha256);
    const presentations = paints.filter(p => p.url === load.url);
    if (responses.length !== 1 || presentations.length !== 1) {
      incomplete.push('ambiguous-or-missing-response-presentation'); continue;
    }
    const response = responses[0], paint = presentations[0];
    const sourceAt = Number(response.captured_at);
    if (!(response.status === 200 && response.captured_at && Number.isFinite(sourceAt) && sourceAt > 0)
        || identities.has(response.captured_at)) {
      incomplete.push('source-frame-identity-unconfirmed'); continue;
    }
    identities.add(response.captured_at);
    if (!(Number.isFinite(paint.presentationTime) && paint.presentationTime > 0
          && paint.presentationTime >= paint.loadTime && paint.presentationTime <= paint.observed_at)) {
      incomplete.push('presentation-time-unavailable'); continue;
    }
    const sample = { presented_at_ms: paint.presentationTime, response_id: response.id,
      presentation_confirmed: true, fresh_frame_identity_confirmed: true,
      source_received_at: response.captured_at, source_identity_scope: 'BACKEND_FRAME_RECEIPT_NOT_SENSOR_SAMPLE_ID',
      visible: paint.visible, occluded: paint.dom_occluded,
      blob_sha256: load.sha256, blob_url: load.url };
    // Keep completions after cutoff as tail evidence, outside the measured window.
    if(paint.presentationTime > raw.dom.window_end_ms) tailPresentations.push(sample);
    else samples.push(sample);
  }
  samples.sort((a, b) => a.presented_at_ms - b.presented_at_ms);
  if (raw.dom?.states.filter(e => e.at <= raw.dom.window_end_ms)
      .some(e => !e.visible || !e.focused || e.dom_occluded || !e.image_present)) {
    incomplete.push('visibility-focus-or-dom-occlusion');
  }
  if (samples.length < 2) incomplete.push('insufficient-presentation-records');
  if (raw.context !== 'FIELD_VISIBLE_PC') incomplete.push('not-field-context');
  // Browser APIs do not certify Windows occlusion, monitor output, or white-screen absence.
  incomplete.push('independent-window-and-white-screen-evidence-required');
  return { status: 'INCOMPLETE', scope: 'BROWSER_PRESENTATION_COMPONENT_ONLY',
    incomplete: [...new Set(incomplete)], samples, loads: inWindowLoads.length,
    paints: paints.length, tail_presentations: tailPresentations,
    actual_screen_and_white_screen_status: 'NOT_EVALUATED',
    release_gate: 'HOLD', promotion_allowed: false };
}

async function observePresentation(page, { durationMs, runId, imageOrigin, context = 'UNSPECIFIED' }) {
  if (!Number.isInteger(durationMs) || durationMs < 500 || durationMs > 900000
      || !/^[A-Za-z0-9_-]{1,80}$/.test(runId)) throw new Error('Bounded duration and run ID required');
  const origin = resolveImageOrigin(page.url(), imageOrigin);
  const hashBinding = '__sflPresentationHash_' + runId;
  const raw = { schema: 'sfl-image-presentation-v1', run_id: runId, context, page_url: page.url(),
    responses: [], errors: [], dom: null };
  const pending = new Set(); let active = true;
  const responseListener = response => {
    const url = new URL(response.url());
    if (!active || url.origin !== origin || url.pathname !== '/api/spot/live_image.jpg') return;
    if (raw.responses.length >= MAX_EVENTS) { raw.errors.push('response-overflow'); active=false; return; }
    const operation = response.allHeaders().then(headers => {
      raw.responses.push({url:response.url(),status:response.status(),captured_at:headers['x-spot-image-at']??null});
    }).catch(error=>raw.errors.push('response-headers: '+error.message));
    pending.add(operation); operation.finally(()=>pending.delete(operation));
  };
  const failedListener = request => {
    const url=new URL(request.url());
    if(active && url.origin===origin && url.pathname==='/api/spot/live_image.jpg') raw.errors.push('image-request-failed');
  };
  page.on('response',responseListener);
  page.on('requestfailed',failedListener);
  try {
    // LAN HTTP pages have no Web Crypto subtle API. This pure hash binding gives
    // the page no file, process, network, or authentication capability.
    await page.exposeFunction(hashBinding, base64 => {
      if (typeof base64 !== 'string' || base64.length > 2800000) throw new Error('Bounded blob required');
      const data = Buffer.from(base64, 'base64');
      if (data.length > 2 * 1024 * 1024) throw new Error('Blob too large');
      return createHash('sha256').update(data).digest('hex');
    });
    await bounded(page.evaluate(({ key, duration, token, maximum, hashFunction, origin }) => {
      if (window[key]) throw new Error('Presentation observer already exists');
      if (!PerformanceObserver.supportedEntryTypes.includes('element')) throw new Error('Element Timing unsupported');
      const target = document.querySelector('img.camera-image');
      if (!target) throw new Error('Visible camera image required');
      const original = target.getAttribute('elementtiming');
      const state = { loads: [], paints: [], states: [], responses: [], errors: [], overflow: false,
        clock: 'PAGE_MONOTONIC_MS', time_origin_epoch_ms: performance.timeOrigin,
        window_start_ms: performance.now(), window_end_ms: null, stopped: false, pending: 0 };
      let closed = false, timer;
      function push(array, value) {
        if (array.length >= maximum) { state.overflow = true; return; }
        array.push(value);
      }
      function visibility() {
        const box = target.getBoundingClientRect();
        const style = getComputedStyle(target);
        // The shipped camera has controls at its upper edge. Inspect the image
        // interior instead of misclassifying those controls as a hidden image.
        // These three DOM points are not a whole-window/physical-screen proof.
        const points = [[.5,.5],[.25,.25],[.75,.75]]
          .map(([x,y]) => [box.left + box.width*x, box.top + box.height*y]);
        const occluded = points.some(([x,y]) => document.elementFromPoint(x,y) !== target);
        return { at: performance.now(), visible: document.visibilityState === 'visible',
          focused: document.hasFocus(), dom_occluded: occluded,
          image_present: target.isConnected && target.complete && target.naturalWidth > 0
            && box.width > 0 && box.height > 0 && style.display !== 'none'
            && style.visibility === 'visible' && Number(style.opacity) > 0 };
      }
      const observeState = () => push(state.states, visibility());
      async function hash(buffer) {
        if (buffer.byteLength > 2 * 1024 * 1024) throw new Error('Blob too large');
        const bytes = new Uint8Array(buffer); let binary = '';
        for (let i=0;i<bytes.length;i+=32768) binary += String.fromCharCode(...bytes.subarray(i,i+32768));
        return window[hashFunction](btoa(binary));
      }
      // Observe bytes the application already consumes. Do not clone/reissue HTTP,
      // change returned bytes/errors, or await the observer before returning them.
      const nativeArrayBuffer = Response.prototype.arrayBuffer;
      const nativeBlob = Response.prototype.blob;
      function capture(response, value, blob) {
        try {
          const url = new URL(response.url);
          if (closed || url.origin !== origin || url.pathname !== '/api/spot/live_image.jpg') return;
          const row = {id:String(state.responses.length),url:response.url,status:response.status,
            captured_at:response.headers.get('X-Spot-Image-At'),at:performance.now()};
          push(state.responses,row); state.pending++;
          Promise.resolve().then(()=>blob?value.arrayBuffer():value).then(hash)
            .then(digest=>{row.sha256=digest;}).catch(error=>{row.error=error.message;})
            .finally(()=>{state.pending--;});
        } catch (error) { push(state.errors,error.message); }
      }
      function arrayBufferObserved(...args) {
        return nativeArrayBuffer.apply(this,args).then(value=>{capture(this,value,false);return value;});
      }
      function blobObserved(...args) {
        return nativeBlob.apply(this,args).then(value=>{capture(this,value,true);return value;});
      }
      Response.prototype.arrayBuffer=arrayBufferObserved;
      Response.prototype.blob=blobObserved;
      const listener = event => {
        if (event.target !== target || closed || performance.now()>state.window_start_ms+duration) return;
        const row={url:target.currentSrc||target.src,at:performance.now()}; push(state.loads,row);
        if (!row.url.startsWith('blob:')) {row.error='Expected local blob URL';return;}
        state.pending++;
        fetch(row.url).then(response=>nativeArrayBuffer.call(response)).then(hash)
          .then(digest=>{row.sha256=digest;}).catch(error=>{row.error=error.message;})
          .finally(()=>{state.pending--;});
      };
      const observer = new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          if (entry.identifier !== token || entry.element !== target || closed) continue;
          push(state.paints, { ...entry.toJSON(), ...visibility(), observed_at: performance.now() });
        }
      });
      observer.observe({ type: 'element', buffered: false });
      target.setAttribute('elementtiming', token);
      document.addEventListener('load', listener, true);
      document.addEventListener('visibilitychange', observeState);
      window.addEventListener('focus', observeState); window.addEventListener('blur', observeState);
      observeState();
      const interval = setInterval(observeState, 100);
      function stop() {
        if (closed) return state;
        state.window_end_ms = state.window_start_ms + duration;
        observeState(); closed = true;
        clearInterval(interval); clearTimeout(timer); observer.disconnect();
        document.removeEventListener('load', listener, true);
        document.removeEventListener('visibilitychange', observeState);
        window.removeEventListener('focus', observeState); window.removeEventListener('blur', observeState);
        if (target.getAttribute('elementtiming') === token) {
          if (original === null) target.removeAttribute('elementtiming'); else target.setAttribute('elementtiming', original);
        }
        if(Response.prototype.arrayBuffer===arrayBufferObserved) Response.prototype.arrayBuffer=nativeArrayBuffer;
        else push(state.errors,'arrayBuffer observer replaced externally');
        if(Response.prototype.blob===blobObserved) Response.prototype.blob=nativeBlob;
        else push(state.errors,'blob observer replaced externally');
        delete window[hashFunction]; // Also remove the binding on the page watchdog path.
        state.stopped = true;
        return state;
      }
      window[key] = { state, stop };
      timer = setTimeout(stop, duration + 2000);
    }, { key: KEY, duration: durationMs, token: runId, maximum: MAX_EVENTS, hashFunction: hashBinding, origin }),5000);
    await new Promise(resolve => setTimeout(resolve, durationMs + 2100));
    raw.dom = await bounded(page.evaluate(key => {
      const handle = window[key]; if (!handle) throw new Error('Observer disappeared');
      const state = handle.stop(); delete window[key]; return state;
    }, KEY),5000);
    if (raw.dom.pending) raw.errors.push('unfinished-blob-hashes');
  } catch (error) { raw.errors.push(error.message); }
  finally {
    active = false; page.off('response',responseListener);
    page.off('requestfailed',failedListener);
    await bounded(Promise.allSettled([...pending]),5000).catch(error=>raw.errors.push(error.message));
    if (pending.size) raw.errors.push('unfinished-response-headers');
    try { await bounded(page.evaluate(({key, binding}) => {
      if (window[key]) { window[key].stop(); delete window[key]; }
      delete window[binding];
    }, {key: KEY, binding: hashBinding}),5000); }
    catch (error) { raw.errors.push('cleanup: ' + error.message); }
  }
  raw.network_responses=raw.responses;
  raw.responses=raw.dom?.responses??[];
  raw.errors.push(...(raw.dom?.errors??[]));
  for(const row of raw.network_responses) if(row.status!==200) raw.errors.push('image-http-error');
  for(const row of raw.responses) {
    const matching=raw.network_responses.filter(n=>n.url===row.url&&n.status===row.status&&n.captured_at===row.captured_at);
    if(matching.length!==1) raw.errors.push('response-headers-not-independently-bound');
  }
  raw.summary = correlatePresentation(raw);
  return raw;
}

function parseArguments(argv) {
  const options = {};
  const required = ['--cdp','--page-url','--client-id','--run-id','--duration-ms','--out','--expected-build'];
  for (let i=0;i<argv.length;i+=2) {
    const key=argv[i];
    if (![...required,'--image-origin'].includes(key) || !argv[i+1] || Object.hasOwn(options,key)) {
      throw new Error('Unexpected, repeated, or incomplete argument');
    }
    options[key]=argv[i+1];
  }
  if (!required.every(key=>options[key])) throw new Error('Missing required argument');
  const cdp=new URL(options['--cdp']);
  if(cdp.protocol!=='http:' || !['127.0.0.1','localhost'].includes(cdp.hostname)
      || !cdp.port || cdp.port==='0' || cdp.pathname!=='/' || cdp.username || cdp.password || cdp.search || cdp.hash) {
    throw new Error('An existing local CDP endpoint is required');
  }
  for(const key of ['--client-id','--run-id']) if(!/^[A-Za-z0-9_-]{1,80}$/.test(options[key])) throw new Error('Invalid identifier');
  if(options['--expected-build']!=='cd46692ac9c551080c57d8168fa9ea5abd530206') throw new Error('This approved probe is bound to C32');
  const duration=Number(options['--duration-ms']);
  if(!Number.isInteger(duration)||duration<500||duration>900000) throw new Error('Bounded duration required');
  resolveImageOrigin(options['--page-url'],options['--image-origin']);
  const destination=options['--out'];
  if(!path.isAbsolute(destination)||fs.existsSync(destination)) throw new Error('New absolute output path required');
  const parent=fs.lstatSync(path.dirname(destination));
  if(!parent.isDirectory()||parent.isSymbolicLink()) throw new Error('Existing output directory required');
  return options;
}

async function main(argv) {
  const options=parseArguments(argv), output=options['--out'];
  // Reserve before attachment. Existing results are never overwritten.
  const fd=fs.openSync(output,'wx'); let browser;
  const result={schema:'sfl-presentation-run-v1',scope:'BROWSER_PRESENTATION_COMPONENT_ONLY',
    client_id:options['--client-id'],observer_hostname:os.hostname(),run_id:options['--run-id'],
    started_utc:new Date().toISOString(),expected_build:options['--expected-build'],
    collector_sha256:createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
    context:'FIELD_CONNECTION_NOT_VISUALLY_ATTESTED',release_gate:'HOLD',promotion_allowed:false};
  try {
    const {chromium}=require('playwright');
    browser=await chromium.connectOverCDP(options['--cdp'],{noDefaults:true,timeout:10000});
    result.browser_version=browser.version();
    const pages=browser.contexts().flatMap(c=>c.pages()).filter(p=>p.url()===options['--page-url']);
    if(pages.length!==1) throw new Error('Exactly one existing target page required');
    const page=pages[0], origin=resolveImageOrigin(page.url(),options['--image-origin']);
    async function identity() {
      const response=await page.request.get(origin+'/health',{timeout:5000,maxRedirects:0});
      try {
        if(response.status()!==200) throw new Error('Health identity unavailable');
        const value=await response.json(), spot=value.spot_temperature;
        const binding={build:spot?.build_git_commit,logger:spot?.v2_4_operational?.logger_service_instance_id};
        if(binding.build!==options['--expected-build']||typeof binding.logger!=='string'
            || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(binding.logger)) throw new Error('Runtime build/logger identity mismatch');
        return binding;
      } finally {await response.dispose();}
    }
    result.before=await identity();
    result.observation=await observePresentation(page,{durationMs:Number(options['--duration-ms']),
      runId:options['--run-id'],imageOrigin:options['--image-origin']});
    result.after=await identity();
    if(JSON.stringify(result.before)!==JSON.stringify(result.after)) throw new Error('Runtime generation changed');
    const captureGaps=result.observation.summary.incomplete.filter(reason=>
      !['not-field-context','independent-window-and-white-screen-evidence-required'].includes(reason));
    result.status=captureGaps.length ? 'CAPTURE_INCOMPLETE' : 'CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE';
  } catch(error) {result.status='CAPTURE_INCOMPLETE';result.error=error.message;}
  finally {
    if(browser) await browser.close().catch(error=>{result.disconnect_error=error.message;});
    result.ended_utc=new Date().toISOString();
    const bytes=Buffer.from(JSON.stringify(result,null,2)+'\n');
    try {fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);} finally {fs.closeSync(fd);}
    console.log(JSON.stringify({result_path:output,sha256:createHash('sha256').update(bytes).digest('hex'),
      status:result.status,release_gate:'HOLD',promotion_allowed:false}));
    process.exitCode=result.status==='CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE'&&!result.disconnect_error ? 0 : 1;
  }
}

module.exports = { observePresentation, correlatePresentation, parseArguments };
if(require.main===module) main(process.argv.slice(2)).catch(error=>{console.error(error.message);process.exitCode=1;});
