import React, {createRef} from 'react';
import {act, cleanup, render} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {writeFileSync, mkdirSync} from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import {apiClient} from '../../../shared/api/client';
import {useSystemViewModel} from './useSystemViewModel';
import {DashboardHeader} from '../../Layout/components/DashboardHeader/DashboardHeader';
import {useDashboardStore} from '../../../store/useDashboardStore';

const ROOT = process.env.SFL_UI_POLL_EVIDENCE_DIR;
const BASE = Date.parse('2026-10-02T06:00:00Z');
const originalAdapter = apiClient.defaults.adapter;
const results: any[] = [];
const noop = () => undefined;
let latestVm: ReturnType<typeof useSystemViewModel>;
let externalNetworkAttempts = 0;
let visibility: DocumentVisibilityState = 'visible';
const spotConfig = {image_url:'/synthetic-image', refresh_interval:1, crosshair_x:0.5, crosshair_y:0.5,
  crosshair_color:'lime', crosshair_thickness:2, crosshair_size:20, crosshair_gap:5,
  widget_width:512, widget_height:288, focus_step:5, actuator_step:5, focus_enabled:true};
const data: any = {Time:'synthetic', Status:'Running', Speed:2.8, Press:165, Count:5,
  EndPos:1015, Spot:540, operator_metadata_valid:true, operator_metadata_missing_fields:[]};

function Harness() {
  const vm = useSystemViewModel();
  latestVm = vm;
  const source = {health:vm.health, stats:vm.stats,
    healthPollingDegraded:vm.healthPolling.degraded,healthPollingIntervalMs:vm.healthPolling.intervalMs,
    healthPollingFailureCount:vm.healthPolling.failureCount,statsPollingDegraded:vm.statsPolling.degraded,
    statsPollingIntervalMs:vm.statsPolling.intervalMs,statsPollingFailureCount:vm.statsPolling.failureCount,
    spotConfig,spotImageUrl:'blob:synthetic-image',spotImageLoading:false,spotImageError:null,
    spotLastSuccessAt:BASE,spotImageMetadata:null,settingsBaseline:null};
  const props: any = {activeCycle:'day',appTitle:'Local production UI reproduction',statusPanelSource:source,
    handleSnapshot:noop,snapshotLoading:false,handleReconnect:noop,reconnectBusy:false,
    handleDiagnosis:noop,diagnosisBusy:false,settingsForm:null,unreadCount:0,notificationsOpen:false,
    setNotificationsOpen:noop,setUnreadCount:noop,clearNotifications:noop,pushNotification:noop,
    menuOpen:false,setMenuOpen:noop,menuRef:createRef(),widgetAddOpen:false,setWidgetAddOpen:noop,
    presetOpen:false,setPresetOpen:noop,layoutEditing:false,setLayoutEditing:noop,
    storageMode:'local',setStorageMode:noop,saveLayout:noop,restoreLayout:noop,deleteLayoutSlot:noop,
    layoutSlots:[],layoutActiveId:null,layoutRestoreMessage:null,layoutSaveMessage:null,
    layoutSaveError:null,layoutRestoreError:null,handleAddWidget:noop,applyPreset:noop,
    themeMode:'light',setThemeMode:noop,handleOpenSettings:noop};
  return <DashboardHeader {...props}/>;
}

beforeEach(() => {
  vi.useFakeTimers();vi.setSystemTime(BASE);
  window.localStorage.clear();window.sessionStorage.clear();
  visibility='visible';
  Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>visibility});
  vi.stubGlobal('BroadcastChannel', undefined);
  // DOM-only synthetic environment. Even unexpected code cannot reach the network.
  externalNetworkAttempts=0;
  const denied=()=>{externalNetworkAttempts++;throw new Error('External network forbidden');};
  vi.spyOn(XMLHttpRequest.prototype,'send').mockImplementation(denied);
  vi.spyOn(http,'request').mockImplementation(denied as any);
  vi.spyOn(https,'request').mockImplementation(denied as any);
  vi.stubGlobal('fetch',vi.fn(async (url,options) => {
    if(String(url).endsWith('/api/log/status') && options?.method==='POST') {
      return {ok:true,json:async()=>({})}; // Header status log; memory only, no request sent.
    }
    return denied();
  }));
  useDashboardStore.setState({data,connected:true,lastDataAt:BASE,pollingDegraded:false,pollingIntervalMs:200,pollingFailureCount:0});
});

afterEach(() => {
  cleanup();apiClient.defaults.adapter=originalAdapter;
  vi.clearAllTimers();vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals();
  if (ROOT) writeFileSync(ROOT+'/results.json',JSON.stringify({scope:'Synthetic transport/clock through actual production React view-model, polling effect, header tick, status hook and badge',results},null,2)+'\n');
});

type Scenario = {name:string,latencyMs:number,initialAgeMs:number,durationMs:number,
  freezeAtMs?:number,recoverAtMs?:number,failHealthNumbers?:number[],hideAtMs?:number,showAtMs?:number,
  firstLatencyMs?:number,wallJumpAtMs?:number,wallJumpMs?:number};

async function exercise(s:Scenario) {
  const requests:any[]=[];const frames:any[]=[];const transitions:any[]=[];
  let healthRequests=0;let activeHealth=0;let maxActiveHealth=0;
  const cycleOrigin=performance.now();
  const elapsed=()=>Math.round(performance.now()-cycleOrigin);
  const sourceAt=(t:number) => {
    const observationT=s.freezeAtMs!==undefined && t>=s.freezeAtMs && (s.recoverAtMs===undefined || t<s.recoverAtMs) ? s.freezeAtMs : t;
    return Math.floor((observationT+s.initialAgeMs)/1000)*1000-s.initialAgeMs;
  };
  apiClient.defaults.adapter=(config:any)=>{
    expect(config.method).toBe('get');
    expect(['/health','/stats']).toContain(config.url);
    const started=elapsed();
    const number=config.url==='/health'?++healthRequests:null;
    const captured=sourceAt(started);
    const responseData=config.url==='/health'?{
      running:true,thread_alive:true,driver_connected:true,mode:'auto',last_update:Date.now()/1000,
      driver_snapshot_age_sec:0.1,comm:{
        extruder:{connected:true,last_success_time:Date.now()/1000,read_failures:0},
        ls_plc:{connected:true,last_success_time:Date.now()/1000,read_failures:0},
        spot:{last_value:540,last_success_time:(Date.now()-started+captured)/1000,last_error_time:null,read_failures:0},
      },
    }:{uptime_sec:30,total_requests:100,avg_latency_ms:2,error_count:0,
        last:{latency_ms:2,path:'/api/latest',status:200,timestamp:Date.now()/1000},
        window:{window_sec:60,request_count:100,http_error_count:0,error_count:0,error_rate:0,p95_latency_ms:3},
        errors:{queue_size:0,last_error_at:null,source_counts:{}}};
    const event={path:config.url,number,started_ms:started,completed_ms:null as number|null,
      source_last_success_ms:config.url==='/health'?captured:null,
      timeout_ms:config.timeout,outcome:'pending'};
    requests.push(event);
    if(number!==null){activeHealth++;maxActiveHealth=Math.max(maxActiveHealth,activeHealth);}
    return new Promise((resolve,reject)=>{
      const complete=()=>{
        event.completed_ms=elapsed();
        if(number!==null)activeHealth--;
        if(number!==null && s.failHealthNumbers?.includes(number)) {
          event.outcome='synthetic-health-error';reject(new Error('Synthetic health endpoint failure'));return;
        }
        event.outcome='success';resolve({status:200,statusText:'OK',data:responseData,headers:{},config});
      };
      const delay=config.url==='/health'?(number===1?s.firstLatencyMs??s.latencyMs:s.latencyMs):0;
      // A zero-latency control settles immediately; nested setTimeout(0) adds
      // one millisecond in Sinon and is not an immediate-response fixture.
      if(delay===0)complete();else window.setTimeout(complete,delay);
    });
  };
  const view=render(<Harness/>);
  const observe=()=>{
    const t=elapsed();
    const badge=view.container.querySelector('[aria-label^="SPOT "]')?.getAttribute('aria-label') ?? null;
    const text=view.container.textContent ?? '';
    const comm=text.includes('Comm 1!')?'Comm 1!':text.includes('Comm OK')?'Comm OK':'other';
    const healthLast=latestVm.health?.comm?.spot?.last_success_time;
    const frame={at_ms:t,badge,comm,backend_current_last_success_ms:sourceAt(t),backend_age_ms:t-sourceAt(t),
      displayed_health_last_success_ms:healthLast==null?null:Math.round(healthLast*1000-BASE),
      health_failures:latestVm.healthPolling.failureCount,health_interval_ms:latestVm.healthPolling.intervalMs,
      paused:latestVm.pollingPausedByVisibility,leader:latestVm.dashboardLeaderState?.mode,
      moving:useDashboardStore.getState().data?.Speed===2.8};
    frames.push(frame);
    if(!transitions.length || transitions[transitions.length-1].badge!==badge) {
      transitions.push(frame);
      if(ROOT && (badge==='SPOT STALE' || (badge==='SPOT OK' && transitions.some(x=>x.badge==='SPOT STALE')))) {
        mkdirSync(ROOT+'/dom',{recursive:true});
        writeFileSync(`${ROOT}/dom/${s.name}-${t}.html`,view.container.innerHTML);
      }
    }
  };
  try {
    await act(async()=>{await vi.advanceTimersByTimeAsync(0);});observe();
    for(let t=50;t<=s.durationMs;t+=50) {
      await act(async()=>{
        await vi.advanceTimersByTimeAsync(50);
        // External data feed: active process data remains current independently of /health.
        if(t%200===0)useDashboardStore.getState().setData({...data,Time:String(t)},Date.now());
        if(t===s.wallJumpAtMs)vi.setSystemTime(Date.now()+(s.wallJumpMs??0));
        if(t===s.hideAtMs || t===s.showAtMs) {
          visibility=t===s.hideAtMs?'hidden':'visible';
          document.dispatchEvent(new Event('visibilitychange'));
        }
      });
      observe();
    }
    expect(externalNetworkAttempts).toBe(0);
    const broadcastBeforeUnmount=window.localStorage.getItem('dashboard_system_broadcast_v1');
    const record={...s,requests,transitions,frames,externalNetworkAttempts,maxActiveHealth,broadcastBeforeUnmount};results.push(record);
    return record;
  } finally {
    view.unmount();
    // Transport response timers finish before checking the actual production cleanup.
    await act(async()=>{await vi.advanceTimersByTimeAsync(Math.max(s.latencyMs,s.firstLatencyMs??0,1));});
    expect(vi.getTimerCount()).toBe(0);
    expect(externalNetworkAttempts).toBe(0);
  }
}


describe('production health polling to rendered SPOT/Comm badges',()=>{
  it.each([0,100,450,1900])('keeps current SPOT OK with %ims successful responses',async(latencyMs)=>{
    const r=await exercise({name:`healthy-${latencyMs}`,latencyMs,initialAgeMs:800,durationMs:15950});
    expect(r.frames.filter(x=>x.badge==='SPOT STALE')).toHaveLength(0);
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,2000,4000,6000,8000,10000,12000,14000]);
    expect(r.requests.filter(x=>x.path==='/health').every(x=>x.outcome==='success')).toBe(true);
    expect(r.frames.at(-1)?.badge).toBe('SPOT OK');
    expect(r.frames.at(-1)?.health_interval_ms).toBe(2000);
    expect(r.maxActiveHealth).toBe(1);
    // /stats cadence is independent and remains unchanged.
    expect(r.requests.filter(x=>x.path==='/stats').map(x=>x.started_ms)).toEqual([500,5500,10500,15500]);
  });
  it('warns at the existing threshold for frozen source, then recovers',async()=>{
    const r=await exercise({name:'source-freeze-control',latencyMs:100,initialAgeMs:0,durationMs:19000,freezeAtMs:2000,recoverAtMs:17000});
    expect(r.frames.filter(x=>x.at_ms>=8000 && x.at_ms<17000).every(x=>x.badge==='SPOT STALE' && x.comm==='Comm 1!')).toBe(true);
    expect(r.transitions.find(x=>x.badge==='SPOT STALE')?.at_ms).toBe(8000);
    expect(r.frames.at(-1)?.badge).toBe('SPOT OK');
    expect(r.maxActiveHealth).toBe(1);
  });
  it('preserves failure backoff, stale warning and recovery',async()=>{
    const r=await exercise({name:'health-failure-control',latencyMs:100,initialAgeMs:0,durationMs:21000,failHealthNumbers:[2,3]});
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,2000,7100,17200,19200]);
    expect(r.frames.some(x=>x.health_failures===2 && x.health_interval_ms===10000 && x.badge==='SPOT STALE')).toBe(true);
    expect(r.frames.at(-1)?.health_failures).toBe(0);
    expect(r.frames.at(-1)?.badge).toBe('SPOT OK');
  });
  it('retains the full 5/10/20/50 second failure backoff sequence',async()=>{
    const r=await exercise({name:'full-backoff',latencyMs:100,initialAgeMs:0,durationMs:89800,failHealthNumbers:[2,3,4,5]});
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,2000,7100,17200,37300,87400,89400]);
    for(const [failureCount,interval] of [[1,5000],[2,10000],[3,20000],[4,50000]]) {
      expect(r.frames.some(x=>x.health_failures===failureCount && x.health_interval_ms===interval)).toBe(true);
    }
    expect(r.frames.at(-1)?.badge).toBe('SPOT OK');
    expect(r.frames.at(-1)?.health_interval_ms).toBe(2000);
  });
  it('pauses health when hidden and refreshes once on visible',async()=>{
    const r=await exercise({name:'visibility-control',latencyMs:100,initialAgeMs:0,durationMs:14000,hideAtMs:1500,showAtMs:9000});
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,9000,11000,13000]);
    expect(r.frames.some(x=>x.paused && x.badge==='SPOT STALE' && x.backend_age_ms<1000)).toBe(true);
    expect(r.frames.at(-1)?.badge).toBe('SPOT OK');
    expect(r.maxActiveHealth).toBe(1);
  });
  it('does not overlap requests when visibility changes during a response',async()=>{
    const r=await exercise({name:'visibility-in-flight',latencyMs:1500,initialAgeMs:0,durationMs:7900,hideAtMs:400,showAtMs:800});
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,2000,4000,6000]);
    expect(r.maxActiveHealth).toBe(1);
    expect(r.frames.at(-1)?.badge).toBe('SPOT OK');
  });
  it('skips missed ticks after a startup overrun instead of issuing a catch-up burst',async()=>{
    const r=await exercise({name:'startup-overrun',latencyMs:100,firstLatencyMs:3500,initialAgeMs:0,durationMs:9800});
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,5500,7500,9500]);
    expect(r.maxActiveHealth).toBe(1);
    expect(r.requests.find(x=>x.path==='/health')?.timeout_ms).toBe(8000);
    expect(r.requests.filter(x=>x.path==='/health').slice(1).every(x=>x.timeout_ms===2000)).toBe(true);
  });
  it.each([-60000,60000])('keeps request cadence after a %ims wall-clock correction',async(wallJumpMs)=>{
    const r=await exercise({name:`wall-${wallJumpMs}`,latencyMs:450,initialAgeMs:0,durationMs:11950,wallJumpAtMs:4200,wallJumpMs});
    expect(r.requests.filter(x=>x.path==='/health').map(x=>x.started_ms)).toEqual([0,2000,4000,6000,8000,10000]);
    expect(r.maxActiveHealth).toBe(1);
  });
  it('unmounts while a response is pending without scheduling another request',async()=>{
    const r=await exercise({name:'unmount-in-flight',latencyMs:1500,initialAgeMs:0,durationMs:500});
    expect(r.requests.filter(x=>x.path==='/health')).toHaveLength(1);
    // exercise unmounts, releases the transport, and asserts no timers or network escape.
    expect(window.localStorage.getItem('dashboard_system_broadcast_v1')).toBe(r.broadcastBeforeUnmount);
    expect(JSON.parse(r.broadcastBeforeUnmount ?? '{}').kind).toBe('stats');
  });
});
