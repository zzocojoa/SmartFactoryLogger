// Portable preparation UI only. It neither installs capture hooks nor changes
// focus/visibility. A real page click must satisfy the existing screen checks.
async function waitForManualPresentationStart({clientId, timeoutMs=300000}) {
  if(clientId!=='PC_2'||!Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>300000)
    throw Error('Invalid manual start options');
  const result={schema:'sfl-presentation-manual-start-v1',status:'WAITING',
    clock:'PAGE_MONOTONIC_MS',started_ms:performance.now(),timeout_ms:timeoutMs,states:[]};
  const panel=document.createElement('div');
  panel.dataset.sflPresentationManualStart='v1';
  panel.style.cssText='position:fixed;z-index:2147483647;width:340px;height:120px;box-sizing:border-box;padding:8px;background:#132333;color:white;font:13px/18px sans-serif;border:2px solid #67cf9c';
  const notice=document.createElement('div'), start=document.createElement('button'), cancel=document.createElement('button');
  notice.style.whiteSpace='pre-line';
  start.textContent='15분 측정 시작';cancel.textContent='취소';
  start.type=cancel.type='button';
  panel.append(notice,start,cancel);
  let timer,finish,finished=false;
  function snapshot(event) {
    const target=document.querySelector('img.camera-image');
    const box=target?.getBoundingClientRect(),style=target&&getComputedStyle(target);
    const present=!!(target?.isConnected&&box.width>0&&box.height>0&&style.display!=='none'
      &&style.visibility==='visible'&&Number(style.opacity)>0);
    return {at:performance.now(),visible:document.visibilityState==='visible',focused:document.hasFocus(),
      dom_present:present,dom_occluded:!present||[[.5,.5],[.25,.25],[.75,.75]].some(([x,y])=>
        document.elementFromPoint(box.left+box.width*x,box.top+box.height*y)!==target),
      event_type:event?.type||'poll',trusted:event?event.isTrusted:null,
      active_element_tag:document.activeElement?.tagName||null};
  }
  function record(event) {
    const state=snapshot(event);result.states.push(state);
    const seconds=Math.max(0,Math.ceil((timeoutMs-(state.at-result.started_ms))/1000));
    notice.textContent=clientId+' · 아직 측정 전입니다.\n아래 시작 버튼을 눌러 주세요.\n'
      +'화면 '+(state.visible?'보임':'숨김')+' · 입력 초점 '+(state.focused?'있음':'없음')
      +' · 준비 대기 '+seconds+'초';
    return state;
  }
  function clicked(event) {
    if(finished)return;
    const state=record(event);
    if(state.at-result.started_ms>=timeoutMs){finish('NOT_READY');return;}
    if(event.isTrusted&&state.visible&&state.focused&&state.dom_present&&!state.dom_occluded)
      finish('READY');
  }
  function cancelled(event) {if(event.isTrusted&&!finished){record(event);finish('CANCELLED');}}
  try {
    const box=document.querySelector('img.camera-image')?.getBoundingClientRect();
    const position=box&&[[8,8],[innerWidth-348,8],[8,innerHeight-128],[innerWidth-348,innerHeight-128]].find(([x,y])=>
      x>=0&&y>=0&&(x+340<=box.left||x>=box.right||y+120<=box.top||y>=box.bottom));
    if(!position)throw Error('Manual start notice cannot fit outside camera');
    panel.style.left=position[0]+'px';panel.style.top=position[1]+'px';document.body.append(panel);
    await new Promise(resolve=>{
      finish=status=>{if(!finished){finished=true;result.status=status;resolve();}};
      start.addEventListener('click',clicked);cancel.addEventListener('click',cancelled);
      record();
      timer=setInterval(()=>{
        const state=record();
        if(state.at-result.started_ms>=timeoutMs)finish('NOT_READY');
        else if(result.states.length>=1500){result.error='manual-start-state-limit';finish('NOT_READY');}
      },250);
    });
  }catch(error){result.status='NOT_READY';result.error=error.message;}
  finally{
    clearInterval(timer);start.removeEventListener('click',clicked);cancel.removeEventListener('click',cancelled);
    panel.remove();result.ended_ms=performance.now();
  }
  return result;
}

module.exports={waitForManualPresentationStart};
