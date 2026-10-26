// V2 component. V1 evidence and its pinned collector remain immutable.
// installPresentationV2 and correlateV2 are self-contained for browser bundling.
function installPresentationV2({durationMs, runId, clientId, origin, hashFunction, readinessMs=10000}) {
  const key='__sflImagePresentationV2', maximum=12000, limit=2097152;
  if(window[key] || window.__sflImagePresentationV1) throw Error('이미 계측 중입니다. 다시 실행하지 마세요.');
  if(!Number.isInteger(durationMs)||durationMs<500||durationMs>900000
      ||!Number.isInteger(readinessMs)||readinessMs<100||readinessMs>10000
      || !/^[A-Za-z0-9_-]{1,80}$/.test(runId)||!/^PC_[1-4]$/.test(clientId)) throw Error('Invalid bounded options');
  if(typeof window[hashFunction]!=='function') throw Error('Hash function required');
  if(!PerformanceObserver.supportedEntryTypes.includes('element')) throw Error('Element Timing unsupported');
  const target=document.querySelector('img.camera-image');
  if(!target) throw Error('Camera image required');
  const originalAttribute=target.getAttribute('elementtiming');
  const native={fetch:window.fetch,Blob:window.Blob,create:URL.createObjectURL,
    arrayBuffer:Response.prototype.arrayBuffer,blob:Response.prototype.blob};
  const responseLinks=new WeakMap(), bufferLinks=new WeakMap(), blobLinks=new WeakMap(), urls=new Map();
  const state={schema:'sfl-presentation-dom-v2',contract_revision:2,loads:[],paints:[],states:[],requests:[],responses:[],object_urls:[],errors:[],
    clock:'PAGE_MONOTONIC_MS',time_origin_epoch_ms:performance.timeOrigin,
    installed_at_ms:performance.now(),readiness_limit_ms:readinessMs,boundary:null,
    window_start_ms:null,window_end_ms:null,requested_duration_ms:durationMs,
    stopped:false,overflow:false,pending:0,early_stop:false};
  let closed=false, interval, timer, observer, sequence=0, badStateSeen=false;
  const panel=document.createElement('div');
  panel.dataset.sflPresentation='v2';
  panel.style.cssText='position:fixed;z-index:2147483647;width:320px;height:64px;box-sizing:border-box;padding:6px;background:#132333;color:white;font:13px/17px sans-serif;border:2px solid #67cf9c;pointer-events:none;white-space:pre-line';
  panel.textContent=clientId+' · 화면 계측 준비 중';
  // Do not cover the measured image or resize the dashboard.
  const imageBox=target.getBoundingClientRect();
  const positions=[[8,8],[innerWidth-328,8],[8,innerHeight-72],[innerWidth-328,innerHeight-72]];
  const position=positions.find(([x,y])=>x>=0&&y>=0
    &&(x+320<=imageBox.left||x>=imageBox.right||y+64<=imageBox.top||y>=imageBox.bottom));
  if(!position) throw Error('계측 안내가 영상을 가립니다. 화면 공간을 확보한 뒤 다시 준비하세요.');
  panel.style.left=position[0]+'px';panel.style.top=position[1]+'px';
  function push(array,value) {
    if(array.length>=maximum){state.overflow=true;return false;}
    array.push(value);return true;
  }
  function error(message){push(state.errors,String(message));}
  function visibility() {
    const box=target.getBoundingClientRect(), style=getComputedStyle(target);
    const present=target.isConnected&&box.width>0&&box.height>0&&style.display!=='none'
      &&style.visibility==='visible'&&Number(style.opacity)>0;
    const occluded=[[.5,.5],[.25,.25],[.75,.75]].some(([x,y])=>
      document.elementFromPoint(box.left+box.width*x,box.top+box.height*y)!==target);
    return {at:performance.now(),visible:document.visibilityState==='visible',focused:document.hasFocus(),
      dom_present:present,dom_occluded:occluded,load_complete:target.complete,
      natural_width:target.naturalWidth,source_url:target.currentSrc||target.src};
  }
  function observeState() {
    const value=visibility();push(state.states,value);
    const bad=!value.visible||!value.focused||!value.dom_present||value.dom_occluded;
    badStateSeen ||= bad;
    const preparing=state.window_start_ms===null;
    const end=preparing?state.installed_at_ms+readinessMs:state.window_start_ms+durationMs;
    const seconds=Math.max(0,Math.ceil((end-performance.now())/1000));
    const text=clientId+(preparing?' · 화면 연결 준비 · 남은 시간 ':' · 측정 중 · 남은 시간 ')+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')
      +'\n'+(bad?'주의: 대시보드 화면을 맨 앞에 유지하세요.':badStateSeen?'숨김/초점 이탈 기록 있음 · 측정은 계속됩니다.':'대시보드를 가리거나 다른 탭으로 바꾸지 마세요.')
      +'\n완료 후 결과 저장 안내가 나타납니다.';
    if(panel.textContent!==text) panel.textContent=text;
    panel.style.borderColor=badStateSeen?'#ffce67':'#67cf9c';
  }
  const hashCallback=window[hashFunction];
  async function hash(buffer) {
    if(buffer.byteLength>limit) throw Error('Blob too large');
    const bytes=new Uint8Array(buffer);let binary='';
    for(let i=0;i<bytes.length;i+=32768) binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    return hashCallback(btoa(binary));
  }
  function digest(row,value,isBlob) {
    state.pending++;
    // Snapshot ArrayBuffer bytes before returning them to the application.
    const task=isBlob?(value.size>limit?Promise.reject(Error('Blob too large')):value.arrayBuffer().then(hash)):hash(value);
    task.then(value=>{row.sha256=value;}).catch(e=>{row.error=e.message;}).finally(()=>{state.pending--;});
  }
  function observedFetch(...args) {
    let image=false;
    try {const url=new URL(args[0] instanceof Request?args[0].url:String(args[0]),location.href);
      image=url.origin===origin&&url.pathname==='/api/spot/live_image.jpg';}catch{}
    const requestStart=performance.now(),task=native.fetch.apply(this,args);
    if(!image||closed) return task;
    const request={id:String(++sequence),started_ms:requestStart,status:'PENDING'};
    push(state.requests,request);
    return task.then(response=>{
      if(!closed) {
        request.status='RESPONSE';request.response_id=request.id;
        const row={id:request.id,url:response.url,status:response.status,
          captured_at:response.headers.get('X-Spot-Image-At'),at:performance.now(),request_started_ms:requestStart,consumed:false};
        if(push(state.responses,row)) responseLinks.set(response,row);
      }
      return response;
    },e=>{if(!closed){request.status='FAILED';error('image-request-failed: '+e.message);}throw e;});
  }
  function consume(response,value,isBlob) {
    if(closed) return;
    const row=responseLinks.get(response);
    if(!row) return; // Pre-install, cloned, or otherwise unsupported responses stay unbound.
    row.consumed=true;row.body_bytes=isBlob?value.size:value.byteLength;
    if(row.body_bytes>limit){row.error='Blob too large';return;}
    (isBlob?blobLinks:bufferLinks).set(value,row.id);
    digest(row,value,isBlob);
  }
  function observedArrayBuffer(...args){return native.arrayBuffer.apply(this,args).then(value=>{
    try{consume(this,value,false);}catch(e){error(e.message);}return value;});}
  function observedBlob(...args){return native.blob.apply(this,args).then(value=>{
    try{consume(this,value,true);}catch(e){error(e.message);}return value;});}
  const ObservedBlob=new Proxy(native.Blob,{construct(Target,args,newTarget){
    const blob=Reflect.construct(Target,args,newTarget);
    try {
      // Only a single full-span part can retain exact lineage. No iteration,
      // byte equality, temporal proximity, or copied/sliced data is guessed.
      const parts=args[0];
      if(!closed&&Array.isArray(parts)&&parts.length===1) {
        const part=Object.getOwnPropertyDescriptor(parts,'0')?.value;
        let id=blobLinks.get(part)||bufferLinks.get(part);
        if(!id&&ArrayBuffer.isView(part)&&part.byteOffset===0&&part.byteLength===part.buffer.byteLength)
          id=bufferLinks.get(part.buffer);
        if(id) blobLinks.set(blob,id);
      }
    }catch(e){error(e.message);}
    return blob;
  }});
  function observedCreate(...args) {
    const url=native.create.apply(this,args);
    if(!closed) {
      const id=blobLinks.get(args[0]);
      if(id) {
        // Object URLs carry a small identity only. Do not retain all image Blobs
        // for fifteen minutes after the application revokes them.
        if(push(state.object_urls,{url,response_id:id,at:performance.now()})) urls.set(url,{id});
      }
    }
    return url;
  }
  function load(event) {
    if(event.target!==target||closed||(state.window_start_ms!==null&&performance.now()>state.window_start_ms+durationMs)) return;
    const row={url:target.currentSrc||target.src,at:performance.now()};
    if(!push(state.loads,row)) return;
    const link=urls.get(row.url);
    if(!link){row.error='response-blob-url-lineage-missing';return;}
    row.response_id=link.id;
    // Local blob URL only: no additional HTTP image request or response clone.
    state.pending++;
    native.fetch.call(window,row.url).then(response=>native.arrayBuffer.call(response)).then(hash)
      .then(value=>{row.sha256=value;}).catch(e=>{row.error=e.message;}).finally(()=>{state.pending--;});
  }
  function imageError(event){if(event.target===target&&!closed) error('image-element-error');}
  function stop(reason='requested') {
    if(closed) return state;
    const now=performance.now(), planned=state.window_start_ms===null?null:state.window_start_ms+durationMs;
    state.window_end_ms=planned===null?null:Math.min(now,planned);
    state.early_stop=planned===null||now<planned;state.stop_reason=reason;
    observeState();closed=true;clearInterval(interval);clearTimeout(timer);observer?.disconnect();
    document.removeEventListener('load',load,true);document.removeEventListener('error',imageError,true);
    document.removeEventListener('visibilitychange',observeState);
    window.removeEventListener('focus',observeState);window.removeEventListener('blur',observeState);
    if(target.getAttribute('elementtiming')===runId) {
      if(originalAttribute===null) target.removeAttribute('elementtiming');
      else target.setAttribute('elementtiming',originalAttribute);
    } else error('elementtiming replaced externally');
    for(const [object,property,ours,original] of [
      [window,'fetch',observedFetch,native.fetch],[window,'Blob',ObservedBlob,native.Blob],
      [URL,'createObjectURL',observedCreate,native.create],
      [Response.prototype,'arrayBuffer',observedArrayBuffer,native.arrayBuffer],
      [Response.prototype,'blob',observedBlob,native.blob]]) {
      if(object[property]===ours) object[property]=original;
      else error(property+' observer replaced externally');
    }
    urls.clear();panel.remove();state.stopped=true;return state;
  }
  try {
    window.fetch=observedFetch;window.Blob=ObservedBlob;URL.createObjectURL=observedCreate;
    Response.prototype.arrayBuffer=observedArrayBuffer;Response.prototype.blob=observedBlob;
    if(window.fetch!==observedFetch||window.Blob!==ObservedBlob||URL.createObjectURL!==observedCreate
      ||Response.prototype.arrayBuffer!==observedArrayBuffer||Response.prototype.blob!==observedBlob)
      throw Error('Required observation hooks unavailable');
    observer=new PerformanceObserver(list=>{
      for(const entry of list.getEntries()) if(!closed&&entry.identifier===runId&&entry.element===target) {
        push(state.paints,{...entry.toJSON(),...visibility(),observed_at:performance.now()});
        const load=state.loads.find(x=>x.url===entry.url&&!x.error&&x.response_id);
        const response=load&&state.responses.find(x=>x.id===load.response_id);
        if(state.window_start_ms===null&&response?.status===200&&response.captured_at
          &&Number(response.captured_at)>0&&Number.isFinite(entry.presentationTime)
          &&entry.presentationTime>0&&entry.presentationTime>=entry.loadTime) {
          state.window_start_ms=entry.presentationTime;
          state.boundary={url:entry.url,response_id:response.id,presentation_time_ms:entry.presentationTime};
          clearTimeout(timer);
          timer=setTimeout(()=>stop('watchdog'),Math.max(0,state.window_start_ms+durationMs+2000-performance.now()));
          observeState();
        }
      }
    });
    observer.observe({type:'element',buffered:false});target.setAttribute('elementtiming',runId);
    document.body.append(panel);
    document.addEventListener('load',load,true);document.addEventListener('error',imageError,true);
    document.addEventListener('visibilitychange',observeState);
    window.addEventListener('focus',observeState);window.addEventListener('blur',observeState);
    observeState();interval=setInterval(observeState,100);
    window[key]={state,stop};timer=setTimeout(()=>{error('presentation-readiness-deadline');stop('readiness-deadline');},readinessMs);
  }catch(e){stop('install-error');throw e;}
}

function correlateV2(raw) {
  const dom=raw.dom, incomplete=[...(raw.errors||[]),...(dom?.errors||[])], samples=[],tail=[],repeats=[];
  if(raw.schema!=='sfl-image-presentation-v2'||dom?.schema!=='sfl-presentation-dom-v2'||dom?.contract_revision!==2) incomplete.push('v2-schema-required');
  if(!dom?.stopped||dom.overflow||dom.pending||dom.early_stop) incomplete.push('collector-incomplete');
  const responses=raw.responses||[], responseIds=new Set();
  let lastSource=null,lastHash=null;
  for(const response of responses) if(response.status!==200) incomplete.push('image-http-error');
  const ready=Number.isFinite(dom?.window_start_ms)&&Number.isFinite(dom?.window_end_ms);
  if(!ready) incomplete.push('measurement-boundary-missing');
  if((dom?.requests||[]).some(r=>(!ready||r.started_ms<=dom.window_end_ms)&&r.status==='PENDING'))
    incomplete.push('image-request-unfinished');
  const loads=(dom?.loads||[]).filter(x=>ready&&x.at<=dom.window_end_ms
    &&(x.at>=dom.window_start_ms||x.url===dom.boundary?.url));
  for(const load of loads) {
    const matches=responses.filter(x=>x.id===load.response_id), paints=(dom.paints||[]).filter(x=>x.url===load.url);
    const urls=(dom.object_urls||[]).filter(x=>x.url===load.url&&x.response_id===load.response_id);
    if(load.error||!load.response_id||matches.length!==1||paints.length!==1||urls.length!==1){incomplete.push('response-blob-presentation-unbound');continue;}
    const response=matches[0],paint=paints[0];
    if(!/^[0-9a-f]{64}$/.test(load.sha256)||response.sha256!==load.sha256||response.error||!response.consumed){
      incomplete.push('response-blob-bytes-mismatch');continue;}
    if(response.status!==200||!response.captured_at||!Number.isFinite(Number(response.captured_at))
      ||Number(response.captured_at)<=0||responseIds.has(response.id)){
      incomplete.push('source-frame-identity-unconfirmed');continue;}
    if(!Number.isFinite(paint.presentationTime)||paint.presentationTime<=0||paint.presentationTime<paint.loadTime
      ||paint.presentationTime>paint.observed_at){incomplete.push('presentation-time-unavailable');continue;}
    responseIds.add(response.id);
    const source=Number(response.captured_at);
    if(lastSource!==null&&(source<lastSource||(source===lastSource&&load.sha256!==lastHash))){
      incomplete.push('source-frame-identity-conflict');continue;
    }
    const repeated=source===lastSource;
    lastSource=source;lastHash=load.sha256;
    const sample={presented_at_ms:paint.presentationTime,response_id:response.id,presentation_confirmed:true,
      fresh_frame_identity_confirmed:!repeated,source_received_at:response.captured_at,
      source_identity_scope:'BACKEND_FRAME_RECEIPT_NOT_SENSOR_SAMPLE_ID',blob_url:load.url,blob_sha256:load.sha256,
      visible:paint.visible,occluded:paint.dom_occluded,lineage:'RESPONSE_OBJECT_BODY_BLOB_URL'};
    (paint.presentationTime>dom.window_end_ms?tail:repeated?repeats:samples).push(sample);
  }
  const states=(dom?.states||[]).filter(s=>!ready||(s.at>=dom.window_start_ms&&s.at<=dom.window_end_ms));
  if(!states.length) incomplete.push('state-observation-missing');
  if(states.some(s=>!s.visible||!s.focused||!s.dom_present||s.dom_occluded)) incomplete.push('visibility-focus-or-dom-occlusion');
  const gaps=states.slice(1).map((s,i)=>s.at-states[i].at);
  if(samples.length<2) incomplete.push('insufficient-presentation-records');
  if(raw.context!=='FIELD_VISIBLE_PC') incomplete.push('not-field-context');
  incomplete.push('independent-window-and-white-screen-evidence-required');
  samples.sort((a,b)=>a.presented_at_ms-b.presented_at_ms);
  return {status:'INCOMPLETE',scope:'BROWSER_PRESENTATION_COMPONENT_ONLY',samples,tail_presentations:tail,
    analysis_revision:3,repeated_presentations:repeats,
    loads:loads.length,paints:dom?.paints?.length||0,incomplete:[...new Set(incomplete)],
    loading_state_samples:states.filter(s=>!s.load_complete).length,
    preparation_loads:(dom?.loads||[]).filter(x=>!ready||x.at<dom.window_start_ms&&x.url!==dom.boundary?.url).length,
    state_sampling_max_gap_ms:gaps.length?Math.max(...gaps):null,
    actual_screen_and_white_screen_status:'NOT_EVALUATED',release_gate:'HOLD',promotion_allowed:false};
}

async function observePresentationV2(page,options) {
  const {createHash}=require('node:crypto');
  const {resolveImageOrigin}=require('./observe_operator_image.cjs');
  const key='__sflImagePresentationV2', binding='__sflPresentationHashV2_'+options.runId;
  const raw={schema:'sfl-image-presentation-v2',context:options.context||'UNSPECIFIED',run_id:options.runId,
    page_url:page.url(),responses:[],errors:[],dom:null};
  async function bounded(task){let timer;try{return await Promise.race([task,new Promise((_,reject)=>{
    timer=setTimeout(()=>reject(Error('Observer operation deadline')),5000);})]);}finally{clearTimeout(timer);}}
  try {
    await page.exposeFunction(binding,base64=>{
      if(typeof base64!=='string'||base64.length>2800000) throw Error('Bounded blob required');
      const bytes=Buffer.from(base64,'base64');if(bytes.length>2097152) throw Error('Blob too large');
      return createHash('sha256').update(bytes).digest('hex');
    });
    await bounded(page.evaluate(installPresentationV2,{...options,origin:resolveImageOrigin(page.url(),options.imageOrigin),hashFunction:binding}));
    const ready=await page.waitForFunction(key=>window[key]?.state.window_start_ms!==null||window[key]?.state.stopped,key,
      {timeout:(options.readinessMs??10000)+2500});await ready.dispose();
    const remaining=await bounded(page.evaluate(key=>{const s=window[key].state;
      return s.stopped?0:Math.max(0,s.window_start_ms+s.requested_duration_ms+2100-performance.now());},key));
    await new Promise(resolve=>setTimeout(resolve,remaining));
    raw.dom=await bounded(page.evaluate(key=>window[key].stop(),key));
  }catch(e){raw.errors.push(e.message);}
  finally {
    try {const dom=await bounded(page.evaluate(({key,binding})=>{
      const state=window[key]?.stop('adapter-cleanup');delete window[key];delete window[binding];return state;
    },{key,binding}));if(dom) raw.dom=dom;}
    catch(e){raw.errors.push('cleanup: '+e.message);}
  }
  raw.responses=raw.dom?.responses||[];raw.summary=correlateV2(raw);return raw;
}

// Pre-capture only: observe actual focus/visibility, never change either one.
// Self-contained so the portable browser bundle can preserve the same logic.
async function waitForPresentationReady({clientId,timeoutMs=30000}) {
  if(!/^PC_[1-3]$/.test(clientId)||!Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>30000)
    throw Error('Invalid readiness options');
  const result={schema:'sfl-presentation-preflight-v1',status:'WAITING',clock:'PAGE_MONOTONIC_MS',
    started_ms:performance.now(),timeout_ms:timeoutMs,states:[]};
  const target=document.querySelector('img.camera-image');
  const panel=document.createElement('div');
  panel.dataset.sflPresentationPreflight='v1';
  panel.style.cssText='position:fixed;z-index:2147483647;width:330px;height:72px;box-sizing:border-box;padding:6px;background:#132333;color:white;font:13px/18px sans-serif;white-space:pre-line;pointer-events:none';
  function snapshot() {
    const box=target?.getBoundingClientRect(),style=target&&getComputedStyle(target);
    const present=!!(target?.isConnected&&box.width>0&&box.height>0&&style.display!=='none'
      &&style.visibility==='visible'&&Number(style.opacity)>0);
    return {at:performance.now(),visible:document.visibilityState==='visible',focused:document.hasFocus(),
      dom_present:present,dom_occluded:!present||[[.5,.5],[.25,.25],[.75,.75]].some(([x,y])=>
        document.elementFromPoint(box.left+box.width*x,box.top+box.height*y)!==target)};
  }
  try {
    const box=target?.getBoundingClientRect();
    const position=box&&[[8,8],[innerWidth-338,8],[8,innerHeight-80],[innerWidth-338,innerHeight-80]].find(([x,y])=>
      x>=0&&y>=0&&(x+330<=box.left||x>=box.right||y+72<=box.top||y>=box.bottom));
    if(!position)throw Error('Readiness notice cannot fit outside camera');
    panel.style.left=position[0]+'px';panel.style.top=position[1]+'px';document.body.append(panel);
    while(true) {
      const state=snapshot();result.states.push(state);
      if(state.at-result.started_ms>=timeoutMs){result.status='NOT_READY';break;}
      if(state.visible&&state.focused&&state.dom_present&&!state.dom_occluded){result.status='READY';break;}
      panel.textContent=clientId+' · 측정 시작 전 준비 중\n대시보드의 빈 곳을 한 번 클릭하세요.\n아직 15분 측정은 시작되지 않았습니다.';
      await new Promise(resolve=>setTimeout(resolve,100));
    }
  }catch(error){result.status='NOT_READY';result.error=error.message;}
  finally{panel.remove();result.ended_ms=performance.now();}
  return result;
}

module.exports={installPresentationV2,correlateV2,observePresentationV2,waitForPresentationReady};
