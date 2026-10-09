import React, {createRef} from 'react';
import {act, cleanup, render} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {writeFileSync, mkdirSync} from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import {apiClient} from '../../../shared/api/client';
import {useSystemViewModel} from './useSystemViewModel';
import {systemService} from '../api/systemService';
import {useObservabilityHandlers} from '../../../shared/hooks/useObservabilityHandlers';
import {DashboardHeader} from '../../Layout/components/DashboardHeader/DashboardHeader';
import {useDashboardStore} from '../../../store/useDashboardStore';
import type {HealthSnapshot, SpotTemperatureHealth} from '../../../shared/types';

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

function Harness({headerKey = 0}: {headerKey?: number}) {
  const vm = useSystemViewModel();
  latestVm = vm;
  const source = {health:vm.health, healthReceipt:vm.healthReceipt, stats:vm.stats,
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
  return <DashboardHeader key={headerKey} {...props}/>;
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
  firstLatencyMs?:number,wallJumpAtMs?:number,wallJumpMs?:number,
  spotAt?:(elapsedMs:number)=>Partial<SpotTemperatureHealth>};

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
      spot_temperature: {
        spot_poll_status:'success',spot_raw_validity:'valid_temperature',spot_source_freshness:'fresh',
        temperature_status_shadow:'ok',temperature_value_origin:'current_observation',spot_cache_status:'fresh',
        cache_fallback_allowed:true,spot_snapshot_age_ms:started-captured,spot_value_age_ms:started-captured,
        spot_poll_freshness_threshold_sec:3,spot_cache_expiry_threshold_sec:10,
        ...s.spotAt?.(started),
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
    const temperature=view.container.querySelector('[aria-label^="Temp "]')?.getAttribute('aria-label') ?? null;
    const text=view.container.textContent ?? '';
    const comm=text.includes('Comm 1!')?'Comm 1!':text.includes('Comm OK')?'Comm OK':'other';
    const healthLast=latestVm.health?.comm?.spot?.last_success_time;
    const frame={at_ms:t,badge,temperature,comm,backend_current_last_success_ms:sourceAt(t),backend_age_ms:t-sourceAt(t),
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
  it('accounts for delivery time before showing source freshness or usable cache', async () => {
    const r = await exercise({name:'direct-delivery-age', latencyMs:4000, initialAgeMs:1500, durationMs:4000,
      spotAt: () => ({spot_snapshot_age_ms:1500, spot_value_age_ms:8000,
        temperature_value_origin:'cached_observation', spot_cache_status:'reused',
        cache_fallback_allowed:true, spot_cache_expiry_threshold_sec:10})});
    const delivered = r.frames.find(frame => frame.at_ms === 4000);
    expect(r.requests.find(request => request.path === '/health')?.timeout_ms).toBe(8000);
    expect(delivered?.badge).toBe('SPOT STALE');
    expect(delivered?.temperature).toBe('Temp STALE');
  });

  it('carries direct delivery time to a follower through the actual broadcast payload', async () => {
    const r = await exercise({name:'follower-delivery-age', latencyMs:4000, initialAgeMs:1500, durationMs:4000,
      spotAt: () => ({spot_snapshot_age_ms:1500, spot_value_age_ms:8000,
        temperature_value_origin:'cached_observation', spot_cache_status:'reused',
        cache_fallback_allowed:true, spot_cache_expiry_threshold_sec:10})});
    const payload = JSON.parse(r.broadcastBeforeUnmount!);
    expect(payload.data.spot_temperature.spot_snapshot_age_ms).toBeGreaterThanOrEqual(5500);
    expect(payload.data.spot_temperature.spot_value_age_ms).toBeGreaterThanOrEqual(12000);
    window.localStorage.setItem('dashboard_polling_leader_v1', JSON.stringify({tab_id:'fixture-leader', updated_at:Date.now()}));
    apiClient.defaults.adapter = () => {throw new Error('Unchanged-generation follower must not fetch');};
    const view = render(<Harness/>);
    try {
      await act(async () => {window.dispatchEvent(new StorageEvent('storage', {
        key:'dashboard_system_broadcast_v1', newValue:JSON.stringify({...payload, tab_id:'fixture-leader', sent_at:Date.now()}),
      }));});
      expect(view.container.querySelector('[aria-label^="SPOT "]')?.getAttribute('aria-label')).toBe('SPOT STALE');
      expect(view.container.querySelector('[aria-label^="Temp "]')?.getAttribute('aria-label')).toBe('Temp STALE');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

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
    const staleAt=r.transitions.find(x=>x.badge==='SPOT STALE')?.at_ms;
    // Existing 5s boundary, evaluated on every render (including the 200ms data feed).
    // The frozen response carries server age; elapsed time begins at receipt.
    expect(staleAt).toBeGreaterThan(7100);
    expect(staleAt).toBeLessThanOrEqual(8000);
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
    expect(r.frames.filter(x=>x.at_ms>=4500).every(x=>x.badge==='SPOT OK' && x.temperature==='Temp OK')).toBe(true);
  });
  it.each(['temperature_under_range','temperature_over_range'] as const)('renders fresh %s independently of old valid-temperature history',async(code)=>{
    const r=await exercise({name:code,latencyMs:100,initialAgeMs:0,durationMs:5950,
      spotAt:()=>({spot_raw_validity:'invalid_sentinel',spot_device_status_code:code,
        temperature_value_origin:'none',temperature_status_shadow:'invalid_value',spot_value_age_ms:60000})});
    const expected=code==='temperature_under_range'?'Temp UNDER_RANGE':'Temp OVER_RANGE';
    expect(r.frames.filter(x=>x.at_ms>=100).every(x=>x.badge==='SPOT OK' && x.temperature===expected && x.comm==='Comm OK')).toBe(true);
  });
  it.each([-60000,60000])('still ages frozen observations after a %ims wall-clock correction',async(wallJumpMs)=>{
    const r=await exercise({name:`frozen-wall-${wallJumpMs}`,latencyMs:100,initialAgeMs:0,durationMs:7950,
      freezeAtMs:2000,wallJumpAtMs:4200,wallJumpMs});
    expect(r.frames.at(-1)?.badge).toBe('SPOT STALE');
    expect(r.frames.at(-1)?.temperature).toBe('Temp STALE');
  });
  it('renders a timeout after successful reception immediately and recovers on the next success',async()=>{
    const r=await exercise({name:'success-timeout-recovery',latencyMs:100,initialAgeMs:0,durationMs:5950,
      spotAt:(t)=>t>=2000 && t<4000?{spot_poll_status:'timeout',spot_raw_validity:'not_received',
        temperature_value_origin:'none',spot_cache_status:'empty',temperature_status_shadow:'source_error'}:{}});
    expect(r.frames.find(x=>x.at_ms===2100)?.badge).toBe('SPOT DOWN');
    expect(r.frames.find(x=>x.at_ms===2100)?.temperature).toBe('Temp SOURCE_ERROR');
    expect(r.frames.find(x=>x.at_ms===2100)?.comm).toBe('Comm 1!');
    expect(r.frames.find(x=>x.at_ms===4100)?.badge).toBe('SPOT OK');
    expect(r.frames.at(-1)?.temperature).toBe('Temp OK');
  });
  it('expires reused temperature during a health outage while retaining the known SPOT error',async()=>{
    const r=await exercise({name:'cached-expiry',latencyMs:0,initialAgeMs:0,durationMs:5950,failHealthNumbers:[2],
      spotAt:()=>({spot_poll_status:'timeout',spot_raw_validity:'not_received',
        temperature_value_origin:'cached_observation',spot_cache_status:'reused',spot_value_age_ms:9000})});
    expect(r.frames.find(x=>x.at_ms===1000)?.temperature).toBe('Temp CACHED');
    expect(r.frames.find(x=>x.at_ms===2000)?.temperature).toBe('Temp STALE');
    expect(r.frames.at(-1)?.badge).toBe('SPOT DOWN');
  });
  it('unmounts while a response is pending without scheduling another request',async()=>{
    const r=await exercise({name:'unmount-in-flight',latencyMs:1500,initialAgeMs:0,durationMs:500});
    expect(r.requests.filter(x=>x.path==='/health')).toHaveLength(1);
    // exercise unmounts, releases the transport, and asserts no timers or network escape.
    expect(window.localStorage.getItem('dashboard_system_broadcast_v1')).toBe(r.broadcastBeforeUnmount);
    expect(JSON.parse(r.broadcastBeforeUnmount ?? '{}').kind).toBe('stats');
  });
});

describe('follower health receipt through the actual view-model and header',()=>{
  const followerHealth:HealthSnapshot={running:true,thread_alive:true,driver_connected:true,mode:'auto',last_update:BASE/1000,
    comm:{extruder:{connected:true},ls_plc:{connected:true},spot:{last_success_time:BASE/1000}},
    spot_temperature:{spot_poll_status:'success',spot_raw_validity:'valid_temperature',spot_source_freshness:'fresh',
      temperature_value_origin:'current_observation',spot_snapshot_age_ms:100}};
  const publish=(sentAt:number,health=followerHealth)=>window.dispatchEvent(new StorageEvent('storage',{
    key:'dashboard_system_broadcast_v1',newValue:JSON.stringify({tab_id:'leader-tab',kind:'health',data:health,sent_at:sentAt})}));
  const setup=()=>{
    window.localStorage.setItem('dashboard_polling_leader_v1',JSON.stringify({tab_id:'leader-tab',updated_at:BASE}));
    apiClient.defaults.adapter=()=>{throw new Error('Follower must not fetch');};
    return render(<Harness/>);
  };
  const label=(view:ReturnType<typeof render>)=>view.container.querySelector('[aria-label^="SPOT "]')?.getAttribute('aria-label');
  const transportCases = ['storage', 'BroadcastChannel'].flatMap(transport =>
    ['legacy', 'sequenced'].map(format => ({transport, format})));
  const setupTransport = (transport: string, format = 'sequenced') => {
    const channels: Array<{onmessage: ((event: {data: unknown}) => void) | null}> = [];
    if (transport === 'BroadcastChannel') vi.stubGlobal('BroadcastChannel', class {
      onmessage = null;
      constructor() {channels.push(this);}
      postMessage() {}
      close() {}
    });
    const view = setup();
    const send = (sentAt: unknown, health = followerHealth, sequence = 1, sourceId = 'leader-source') => {
      const payload = {tab_id: 'leader-tab', kind: 'health', data: health, sent_at: sentAt,
        ...(format === 'sequenced' ? {source_id: sourceId, health_sequence: sequence} : {})};
      if (transport === 'BroadcastChannel') channels.at(-1)?.onmessage?.({data: payload});
      else window.dispatchEvent(new StorageEvent('storage', {key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify(payload)}));
    };
    return {view, send};
  };
  const timeoutHealth: HealthSnapshot = {...followerHealth, spot_temperature: {...followerHealth.spot_temperature,
    spot_poll_status: 'timeout', spot_raw_validity: 'not_received', temperature_value_origin: 'none'}};

  it.each(transportCases)('receives timeout and recovery after a backward clock correction via $transport/$format', async ({transport, format}) => {
    const {view, send} = setupTransport(transport, format);
    try {
      await act(async () => {send(BASE);});
      expect(label(view)).toBe('SPOT OK');
      await act(async () => {
        vi.setSystemTime(BASE - 60000);
        await vi.advanceTimersByTimeAsync(2000);
        send(Date.now(), timeoutHealth, 2);
      });
      expect(latestVm.health?.spot_temperature?.spot_poll_status).toBe('timeout');
      expect(label(view)).toBe('SPOT DOWN');
      await act(async () => {await vi.advanceTimersByTimeAsync(2000);send(Date.now(), followerHealth, 3);});
      expect(label(view)).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount();expect(vi.getTimerCount()).toBe(0);}
  });

  const invalidTimingCases = transportCases.flatMap(route => [
    {name: 'future', sentAt: BASE + 60000}, {name: 'missing', sentAt: undefined},
    {name: 'null', sentAt: null}, {name: 'NaN', sentAt: NaN}, {name: 'string', sentAt: String(BASE + 60000)},
  ].map(timing => ({...route, ...timing})));
  it.each(invalidTimingCases)('recovers after $name timing via $transport/$format', async ({transport, format, sentAt}) => {
    const {view, send} = setupTransport(transport, format);
    try {
      await act(async () => {send(sentAt);});
      expect(label(view)).toBe('SPOT UNKNOWN');
      await act(async () => {await vi.advanceTimersByTimeAsync(2000);send(Date.now(), followerHealth, 2);});
      expect(label(view)).toBe('SPOT OK');
      expect(latestVm.healthReceipt?.ageAtReceiptMs).toBe(0);
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount();expect(vi.getTimerCount()).toBe(0);}
  });

  it.each(['storage', 'BroadcastChannel'])('rejects duplicate/older sequences and accepts a new source via %s', async transport => {
    const {view, send} = setupTransport(transport);
    try {
      await act(async () => {send(BASE, timeoutHealth, 2);});
      expect(label(view)).toBe('SPOT DOWN');
      const receipt = latestVm.healthReceipt;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
        send(Date.now(), followerHealth, 1);
        send(Date.now(), followerHealth, 2);
      });
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(label(view)).toBe('SPOT DOWN');
      view.rerender(<Harness headerKey={1}/>);
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async () => {send(Date.now(), followerHealth, 1, 'reloaded-source');});
      expect(label(view)).toBe('SPOT OK');
      const recoveredReceipt = latestVm.healthReceipt;
      await act(async () => {send(Date.now(), timeoutHealth, 2);});
      expect(latestVm.healthReceipt).toBe(recoveredReceipt);
      expect(label(view)).toBe('SPOT OK');
    } finally {view.unmount();expect(vi.getTimerCount()).toBe(0);}
  });

  it('accepts distinct legacy payloads with equal wall-clock timestamps', async () => {
    const {view, send} = setupTransport('storage', 'legacy');
    try {
      await act(async () => {send(BASE);});
      expect(label(view)).toBe('SPOT OK');
      await act(async () => {send(BASE, timeoutHealth);});
      expect(label(view)).toBe('SPOT DOWN');
    } finally {
      view.unmount();
      await act(async () => {await vi.advanceTimersByTimeAsync(0);});
      expect(vi.getTimerCount()).toBe(0);
    }
  });

  it('accounts for delayed broadcasts, rejects duplicates on both transports, and retains age across header remount',async()=>{
    const channels:Array<{onmessage:((event:{data:unknown})=>void)|null}>=[];
    vi.stubGlobal('BroadcastChannel',class {
      onmessage=null;
      constructor(){channels.push(this);}
      postMessage(){}
      close(){}
    });
    const view=setup();
    try {
      await act(async()=>{publish(BASE-6000);});
      expect(label(view)).toBe('SPOT STALE');
      await act(async()=>{publish(BASE);});
      expect(label(view)).toBe('SPOT OK');
      const receipt=latestVm.healthReceipt;
      await act(async()=>{
        await vi.advanceTimersByTimeAsync(5000);
        publish(BASE);
        channels.at(-1)?.onmessage?.({data:{tab_id:'leader-tab',kind:'health',data:followerHealth,sent_at:BASE}});
      });
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(label(view)).toBe('SPOT STALE');
      view.rerender(<Harness headerKey={1}/>);
      expect(label(view)).toBe('SPOT STALE');
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async()=>{publish(Date.now());});
      expect(label(view)).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount();expect(vi.getTimerCount()).toBe(0);}
  });

  it('shows UNKNOWN for invalid broadcast timing and missing diagnostics instead of old success',async()=>{
    const view=setup();
    try {
      await act(async()=>{publish(BASE+1000);});
      expect(label(view)).toBe('SPOT UNKNOWN');
      await act(async()=>{await vi.advanceTimersByTimeAsync(2000);publish(Date.now(),{...followerHealth,spot_temperature:undefined});});
      expect(label(view)).toBe('SPOT UNKNOWN');
    } finally {view.unmount();expect(vi.getTimerCount()).toBe(0);}
  });
  it.each([undefined,null,NaN,String(BASE)])('rejects missing or malformed broadcast sent_at %s',async(sentAt)=>{
    const view=setup();
    try {
      await act(async()=>{
        window.dispatchEvent(new StorageEvent('storage',{key:'dashboard_system_broadcast_v1',
          newValue:JSON.stringify({tab_id:'leader-tab',kind:'health',data:followerHealth,sent_at:sentAt})}));
      });
      expect(label(view)).toBe('SPOT UNKNOWN');
      await act(async()=>{await vi.advanceTimersByTimeAsync(50);});
    } finally {view.unmount();expect(vi.getTimerCount()).toBe(0);}
  });
});

describe('health broadcast observation ordering', () => {
  const currentHealth = (spot: Partial<SpotTemperatureHealth> = {}): HealthSnapshot => ({
    running: true, thread_alive: true, driver_connected: true, mode: 'auto', last_update: BASE / 1000,
    comm: {extruder: {connected: true}, ls_plc: {connected: true}, spot: {last_success_time: BASE / 1000}},
    spot_temperature: {spot_service_instance_id: 'service-a', spot_poll_seq: 10,
      spot_poll_status: 'success', spot_raw_validity: 'valid_temperature', spot_source_freshness: 'fresh',
      temperature_value_origin: 'current_observation', spot_snapshot_age_ms: 100, ...spot},
  });
  const setupOrdering = () => {
    window.localStorage.setItem('dashboard_polling_leader_v1', JSON.stringify({tab_id: 'leader-a', updated_at: BASE}));
    apiClient.defaults.adapter = () => {throw new Error('Follower must not fetch');};
    const view = render(<Harness/>);
    let sequence = 0;
    const send = (health: HealthSnapshot) => window.dispatchEvent(new StorageEvent('storage', {
      key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify({tab_id: 'leader-a', kind: 'health',
        source_id: 'source-a', health_sequence: ++sequence, sent_at: Date.now(), data: health}),
    }));
    const label = () => view.container.querySelector('[aria-label^="SPOT "]')?.getAttribute('aria-label');
    return {view, send, label};
  };

  it.each(['future', 'missing'])('followup same-poll invalid %s timing cannot rejuvenate', async timing => {
    const {view, send, label} = setupOrdering();
    const deliver = (sequence: number, sentAt: number | null, spot: Partial<SpotTemperatureHealth> = {}) => window.dispatchEvent(new StorageEvent('storage', {
      key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify({tab_id: 'leader-a', kind: 'health', source_id: 'source-a',
        health_sequence: sequence, sent_at: sentAt, data: currentHealth({spot_snapshot_age_ms: 1, ...spot})}),
    }));
    try {
      await act(async () => {send(currentHealth()); await vi.advanceTimersByTimeAsync(6000);});
      expect(label()).toBe('SPOT STALE');
      await act(async () => {deliver(2, timing === 'future' ? Date.now() + 60000 : null);});
      expect(label()).toBe('SPOT UNKNOWN');
      await act(async () => {deliver(3, Date.now());});
      expect(label()).toBe('SPOT STALE');
      await act(async () => {deliver(4, Date.now(), {spot_poll_seq: 11});});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup cache age survives invalid timing without aging communication from the cached value', async () => {
    const {view, send, label} = setupOrdering();
    const cached = {temperature_value_origin: 'cached_observation' as const, spot_cache_status: 'reused' as const,
      cache_fallback_allowed: true, spot_cache_expiry_threshold_sec: 10};
    const deliver = (sequence: number, sentAt: number) => window.dispatchEvent(new StorageEvent('storage', {
      key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify({tab_id: 'leader-a', kind: 'health', source_id: 'source-a',
        health_sequence: sequence, sent_at: sentAt, data: currentHealth({...cached, spot_snapshot_age_ms: 1, spot_value_age_ms: 1})}),
    }));
    try {
      await act(async () => {send(currentHealth({...cached, spot_value_age_ms: 9000})); await vi.advanceTimersByTimeAsync(2000);});
      expect(label()).toBe('SPOT OK');
      await act(async () => {deliver(2, Date.now() + 60000);});
      expect(label()).toBe('SPOT UNKNOWN');
      await act(async () => {deliver(3, Date.now());});
      expect(label()).toBe('SPOT OK');
      expect(view.container.querySelector('[aria-label^="Temp "]')?.getAttribute('aria-label')).toBe('Temp STALE');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup delayed startup cannot replace a completed same-poll timeout', async () => {
    const {view, send, label} = setupOrdering();
    try {
      await act(async () => {send(currentHealth({spot_poll_seq: 1, spot_poll_status: 'timeout', spot_raw_validity: 'not_received', temperature_value_origin: 'none'}));});
      expect(label()).toBe('SPOT DOWN');
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(currentHealth({spot_poll_seq: 1, spot_poll_status: 'not_attempted', spot_raw_validity: 'not_received',
        spot_source_freshness: 'unknown', temperature_status_shadow: 'startup_pending', spot_cache_status: 'empty',
        temperature_value_origin: 'none', spot_snapshot_age_ms: null, spot_value_age_ms: null}));});
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async () => {send(currentHealth({spot_poll_seq: 2}));});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup renders UNKNOWN through the header for malformed diagnostic enums', async () => {
    const {view, send, label} = setupOrdering();
    try {
      await act(async () => {send(currentHealth({temperature_status_shadow: {code: 'invalid'}} as unknown as Partial<SpotTemperatureHealth>));});
      expect(label()).toBe('SPOT UNKNOWN');
      expect(view.container.querySelectorAll('.mobile-menu-spot-details dd')).toHaveLength(12);
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup confirms an unseen predecessor without retiring the live service or repeating confirmation', async () => {
    const {view, send, label} = setupOrdering();
    const live = currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:20, spot_poll_status:'timeout'});
    let requests = 0;
    apiClient.defaults.adapter = async config => {requests++; return {data:live, status:200, statusText:'OK', headers:{}, config};};
    try {
      await act(async () => {await latestVm.fetchHealth();});
      expect(label()).toBe('SPOT DOWN');
      await act(async () => {send(currentHealth());});
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-b');
      expect(requests).toBe(2);
      await act(async () => {send(currentHealth({spot_poll_seq:11}));});
      expect(requests).toBe(2);
      await act(async () => {send(currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:21}));});
      expect(label()).toBe('SPOT OK');
      expect(latestVm.dashboardLeaderState?.mode).toBe('follower');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup ignores an earlier direct completion after a later request confirms the live service', async () => {
    const {view, label} = setupOrdering();
    const responders: Array<(health:HealthSnapshot) => void> = [];
    apiClient.defaults.adapter = config => new Promise(resolve => {responders.push(health => resolve({data:health, status:200, statusText:'OK', headers:{}, config}));});
    try {
      let earlier!: Promise<HealthSnapshot | null>;
      let later!: Promise<HealthSnapshot | null>;
      await act(async () => {earlier = latestVm.fetchHealth(); later = latestVm.fetchHealth();});
      await act(async () => {responders[1](currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:20, spot_poll_status:'timeout'})); await later;});
      expect(label()).toBe('SPOT DOWN');
      const receipt = latestVm.healthReceipt;
      await act(async () => {responders[0](currentHealth()); await earlier;});
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-b');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup retains backend stale on the same poll until a new poll recovers', async () => {
    const {view, send, label} = setupOrdering();
    try {
      await act(async () => {send(currentHealth()); await vi.advanceTimersByTimeAsync(3500);
        send(currentHealth({spot_source_freshness:'stale', spot_snapshot_age_ms:3500, spot_poll_freshness_threshold_sec:3}));});
      expect(label()).toBe('SPOT STALE');
      await act(async () => {await vi.advanceTimersByTimeAsync(500); send(currentHealth({spot_snapshot_age_ms:100, spot_poll_freshness_threshold_sec:3}));});
      expect(label()).toBe('SPOT STALE');
      expect(view.container.querySelector('[aria-label^="Temp "]')?.getAttribute('aria-label')).toBe('Temp STALE');
      await act(async () => {send(currentHealth({spot_poll_seq:11, spot_poll_freshness_threshold_sec:3}));});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup lets a latest direct request recover a previously retired actual service', async () => {
    const {view, label} = setupOrdering();
    let response = currentHealth();
    apiClient.defaults.adapter = async config => ({data:response, status:200, statusText:'OK', headers:{}, config});
    try {
      await act(async () => {await latestVm.fetchHealth();});
      response = currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:1, spot_poll_status:'timeout'});
      await act(async () => {await latestVm.fetchHealth();});
      expect(label()).toBe('SPOT DOWN');
      response = currentHealth({spot_poll_seq:11});
      await act(async () => {await latestVm.fetchHealth();});
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-a');
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup retries failed generation confirmation while keeping the current observation', async () => {
    const {view, send, label} = setupOrdering();
    let requests = 0;
    const replacement = currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:1, spot_poll_status:'timeout'});
    apiClient.defaults.adapter = async config => {
      requests++;
      if (requests === 1) throw new Error('Synthetic confirmation failure');
      return {data:replacement, status:200, statusText:'OK', headers:{}, config};
    };
    try {
      await act(async () => {send(currentHealth());});
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(replacement);});
      expect(label()).toBe('SPOT OK');
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async () => {send(replacement);});
      expect(requests).toBe(2);
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.dashboardLeaderState?.mode).toBe('follower');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup defers generation confirmation while hidden and confirms once visible', async () => {
    const {view, send, label} = setupOrdering();
    let requests = 0;
    const replacement = currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:1, spot_poll_status:'timeout'});
    apiClient.defaults.adapter = async config => {requests++; return {data:replacement, status:200, statusText:'OK', headers:{}, config};};
    try {
      await act(async () => {send(currentHealth());});
      await act(async () => {visibility='hidden'; document.dispatchEvent(new Event('visibilitychange')); send(replacement);});
      expect(requests).toBe(0);
      expect(label()).toBe('SPOT OK');
      await act(async () => {visibility='visible'; document.dispatchEvent(new Event('visibilitychange')); send(replacement);});
      expect(requests).toBe(1);
      expect(label()).toBe('SPOT DOWN');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('followup confirms a generation that arrives after the current confirmation started', async () => {
    const {view, send, label} = setupOrdering();
    const responders: Array<(health:HealthSnapshot) => void> = [];
    apiClient.defaults.adapter = config => new Promise(resolve => {responders.push(health => resolve({data:health, status:200, statusText:'OK', headers:{}, config}));});
    const live = currentHealth({spot_service_instance_id:'service-b', spot_poll_seq:20, spot_poll_status:'timeout'});
    const replacement = currentHealth({spot_service_instance_id:'service-c', spot_poll_seq:1, spot_poll_status:'timeout'});
    try {
      await act(async () => {send(live); send(currentHealth());});
      expect(responders).toHaveLength(1);
      await act(async () => {send(replacement); send(replacement);});
      expect(responders).toHaveLength(1);
      await act(async () => {responders[0](live);});
      // B was captured before C arrived; it cannot confirm C as a predecessor.
      expect(responders).toHaveLength(2);
      await act(async () => {responders[1](replacement);});
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-c');
      expect(label()).toBe('SPOT DOWN');
      await act(async () => {send(currentHealth({spot_service_instance_id:'service-c', spot_poll_seq:2}));});
      expect(label()).toBe('SPOT OK');
      expect(latestVm.dashboardLeaderState?.mode).toBe('follower');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });



  it.each(['legacy-interleaved', 'source-replacement', 'leader-replacement'])('%s preserves the latest timeout', async scenario => {
    const channels: Array<{onmessage: ((event: {data: unknown}) => void) | null}> = [];
    vi.stubGlobal('BroadcastChannel', class {
      onmessage = null;
      constructor() {channels.push(this);}
      postMessage() {}
      close() {}
    });
    window.localStorage.setItem('dashboard_polling_leader_v1', JSON.stringify({tab_id: 'leader-a', updated_at: BASE}));
    apiClient.defaults.adapter = () => {throw new Error('Follower must not fetch');};
    const view = render(<Harness/>);
    const normal: HealthSnapshot = {running: true, thread_alive: true, driver_connected: true, mode: 'auto', last_update: BASE / 1000,
      comm: {extruder: {connected: true}, ls_plc: {connected: true}, spot: {last_success_time: BASE / 1000}},
      spot_temperature: {spot_service_instance_id: 'synthetic-service', spot_poll_seq: 10, spot_poll_status: 'success', spot_raw_validity: 'valid_temperature', spot_source_freshness: 'fresh',
        temperature_value_origin: 'current_observation', spot_snapshot_age_ms: 100}};
    const failed: HealthSnapshot = {...normal, spot_temperature: {...normal.spot_temperature,
      spot_poll_seq: 11, spot_poll_status: 'timeout', spot_raw_validity: 'not_received', temperature_value_origin: 'none'}};
    const makePayload = (tab: string, source: string, sequence: number, data: HealthSnapshot, sentAt: number) => ({
      tab_id: tab, kind: 'health', data, sent_at: sentAt,
      ...(scenario === 'legacy-interleaved' ? {} : {source_id: source, health_sequence: sequence}),
    });
    const send = (payload: unknown, transport: 'bc' | 'storage') => {
      if (transport === 'bc') channels.at(-1)?.onmessage?.({data: payload});
      else window.dispatchEvent(new StorageEvent('storage', {key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify(payload)}));
    };
    const label = () => view.container.querySelector('[aria-label^="SPOT "]')?.getAttribute('aria-label');
    try {
      const first = makePayload('leader-a', 'source-a', 1, normal, BASE);
      await act(async () => {send(first, 'bc');});
      expect(label()).toBe('SPOT OK');
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
        if (scenario === 'leader-replacement') {
          window.localStorage.setItem('dashboard_polling_leader_v1', JSON.stringify({tab_id: 'leader-b', updated_at: Date.now()}));
          window.dispatchEvent(new StorageEvent('storage', {key: 'dashboard_polling_leader_v1'}));
        }
        send(makePayload(scenario === 'leader-replacement' ? 'leader-b' : 'leader-a',
          scenario === 'legacy-interleaved' ? 'source-a' : 'source-b', 1, failed, Date.now()), 'bc');
      });
      expect(label()).toBe('SPOT DOWN');
      const timeoutReceipt = latestVm.healthReceipt;
      await act(async () => {send(scenario === 'legacy-interleaved' ? first
        : makePayload('leader-a', 'source-a', 2, normal, BASE), 'storage');});
      console.log('ORDERING_PROBE ' + JSON.stringify({scenario, expected: 'SPOT DOWN', observed: label(),
        poll: latestVm.health?.spot_temperature?.spot_poll_status, delayMs: latestVm.healthReceipt?.ageAtReceiptMs,
        externalNetworkAttempts}));
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.health?.spot_temperature?.spot_poll_seq).toBe(11);
      expect(latestVm.healthReceipt).toBe(timeoutReceipt);
      if (scenario === 'leader-replacement') expect(latestVm.dashboardLeaderState?.leader_tab_id).toBe('leader-b');
      await act(async () => {send(makePayload(scenario === 'leader-replacement' ? 'leader-b' : 'leader-a',
        'source-b', 2, {...normal, spot_temperature: {...normal.spot_temperature, spot_poll_seq: 12}}, Date.now()), 'bc');});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {
      view.unmount();
      await act(async () => {await vi.advanceTimersByTimeAsync(50);});
    }
  });

  it('does not rejuvenate the same poll from a delayed sender, and accepts its later age update', async () => {
    const {view, send, label} = setupOrdering();
    try {
      await act(async () => {send(currentHealth());});
      expect(label()).toBe('SPOT OK');
      await act(async () => {await vi.advanceTimersByTimeAsync(6000);send(currentHealth({spot_snapshot_age_ms: 1}));});
      expect(label()).toBe('SPOT STALE');
      expect(latestVm.health?.spot_temperature?.spot_snapshot_age_ms).toBeGreaterThanOrEqual(6100);
      await act(async () => {send(currentHealth({spot_snapshot_age_ms: 8000}));});
      expect(latestVm.health?.spot_temperature?.spot_snapshot_age_ms).toBe(8000);
      expect(label()).toBe('SPOT STALE');
    } finally {view.unmount();await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('keeps cached value age without making a fresh communication observation stale', async () => {
    const {view, send, label} = setupOrdering();
    const cached = {temperature_value_origin: 'cached_observation' as const, spot_cache_status: 'reused' as const,
      cache_fallback_allowed: true, spot_cache_expiry_threshold_sec: 10};
    try {
      await act(async () => {send(currentHealth({...cached, spot_value_age_ms: 9000}));});
      await act(async () => {await vi.advanceTimersByTimeAsync(2000);
        send(currentHealth({...cached, spot_snapshot_age_ms: 2100, spot_value_age_ms: 1000}));});
      expect(label()).toBe('SPOT OK');
      expect(view.container.querySelector('[aria-label^="Temp "]')?.getAttribute('aria-label')).toBe('Temp STALE');
      expect(latestVm.health?.spot_temperature?.spot_value_age_ms).toBeGreaterThanOrEqual(11000);
    } finally {view.unmount();await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('accepts a restarted service at poll zero and ignores delayed retired-service messages', async () => {
    const {view, send, label} = setupOrdering();
    const restarted = currentHealth({spot_service_instance_id: 'service-b', spot_poll_seq: 0,
      spot_poll_status: 'not_attempted', spot_raw_validity: 'not_evaluated'});
    let confirmations = 0;
    apiClient.defaults.adapter = async config => {
      expect(config.url).toBe('/health');
      confirmations++;
      return {data: restarted, status: 200, statusText: 'OK', headers: {}, config};
    };
    try {
      await act(async () => {send(currentHealth({spot_poll_seq: 100, spot_poll_status: 'timeout'}));});
      expect(label()).toBe('SPOT DOWN');
      await act(async () => {send(restarted);});
      expect(label()).toBe('SPOT WAIT');
      expect(confirmations).toBe(1);
      await act(async () => {send(currentHealth({spot_service_instance_id: 'service-b', spot_poll_seq: 1}));});
      expect(label()).toBe('SPOT OK');
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(currentHealth({spot_poll_seq: 101, spot_poll_status: 'timeout'}));});
      expect(label()).toBe('SPOT OK');
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-b');
      expect(confirmations).toBe(1);
    } finally {view.unmount();await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('preserves API SPOT/receipt ordering while still applying other health fields from an older poll', async () => {
    const {view, send, label} = setupOrdering();
    try {
      const timeout = currentHealth({spot_poll_seq: 11, spot_poll_status: 'timeout'});
      timeout.comm = {...timeout.comm, spot: {read_failures: 7}};
      apiClient.defaults.adapter = async config => ({data: timeout, status: 200, statusText: 'OK', headers: {}, config});
      await act(async () => {await latestVm.fetchHealth();});
      expect(label()).toBe('SPOT DOWN');
      const receipt = latestVm.healthReceipt;
      const older = currentHealth();
      older.comm = {...older.comm, extruder: {connected: false}, spot: {read_failures: 0}};
      await act(async () => {send(older);});
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(latestVm.health?.comm?.spot?.read_failures).toBe(7);
      expect(latestVm.health?.comm?.extruder?.connected).toBe(false);
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount();await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('returns successful manual Diagnosis despite a newer scheduled health poll', async () => {
    const alert = vi.fn().mockResolvedValue(undefined);
    let diagnosis!: ReturnType<typeof useObservabilityHandlers>;
    let finishManual!: () => void;
    let healthRequests = 0;
    const initial = currentHealth();
    const newer = currentHealth({spot_poll_seq: 11, spot_poll_status: 'timeout'});
    apiClient.defaults.adapter = config => {
      const response = (data: unknown) => ({data, status: 200, statusText: 'OK', headers: {}, config});
      if (config.url !== '/health') {
        return Promise.resolve(response({window: {window_sec: 60, request_count: 0, http_error_count: 0}}));
      }
      healthRequests++;
      if (healthRequests === 2) {
        return new Promise(resolve => {finishManual = () => resolve(response(initial));});
      }
      return Promise.resolve(response(healthRequests === 1 ? initial : newer));
    };
    function DiagnosisHarness() {
      const vm = useSystemViewModel();
      latestVm = vm;
      diagnosis = useObservabilityHandlers({fetchHealth: vm.fetchHealth, fetchStats: vm.fetchStats,
        exportObservability: async () => null, clearObservabilityErrors: async () => {},
        openExportFile: async () => {}, openExportFolder: async () => {}, lastExportPath: null,
        modal: {alert}, pushNotification: noop});
      return null;
    }
    const view = render(<DiagnosisHarness/>);
    try {
      await act(async () => {await vi.advanceTimersByTimeAsync(0); await vi.advanceTimersByTimeAsync(1500);});
      let pending!: Promise<void>;
      await act(async () => {pending = diagnosis.handleDiagnosis();});
      expect(healthRequests).toBe(2);
      await act(async () => {await vi.advanceTimersByTimeAsync(500);});
      expect(healthRequests).toBe(3);
      const receipt = latestVm.healthReceipt;
      const broadcast = window.localStorage.getItem('dashboard_system_broadcast_v1');
      await act(async () => {await vi.advanceTimersByTimeAsync(100); finishManual(); await pending;});
      expect(latestVm.health?.spot_temperature?.spot_poll_seq).toBe(11);
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(window.localStorage.getItem('dashboard_system_broadcast_v1')).toBe(broadcast);
      expect(alert).toHaveBeenCalledWith(expect.stringContaining('Mode: auto'));
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('retains interleaved legacy duplicate history without backend identity', async () => {
    const {view, label} = setupOrdering();
    const health = currentHealth({spot_service_instance_id: undefined, spot_poll_seq: undefined});
    const payload = (sentAt: number, data = health) => ({tab_id: 'leader-a', kind: 'health', sent_at: sentAt, data});
    const send = (data: unknown) => window.dispatchEvent(new StorageEvent('storage', {
      key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify(data),
    }));
    try {
      const first = payload(BASE);
      await act(async () => {send(first);
        send(payload(BASE, currentHealth({spot_service_instance_id: undefined, spot_poll_seq: undefined, spot_poll_status: 'timeout'})));
        send(first);});
      expect(label()).toBe('SPOT DOWN');
    } finally {view.unmount();await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  const setupCapacityOrdering = () => {
    const maps = new Set<Map<string, number>>();
    const mapSet = Map.prototype.set;
    vi.spyOn(Map.prototype, 'set').mockImplementation(function (this: Map<string, number>, key: string, value: number) {
      if (typeof key === 'string' && key.includes('capacity-source-') && typeof value === 'number') {
        maps.add(this);
      }
      return mapSet.call(this, key, value);
    });
    const channels: Array<{onmessage: ((event: {data: unknown}) => void) | null}> = [];
    vi.stubGlobal('BroadcastChannel', class {
      onmessage = null;
      constructor() {channels.push(this);}
      postMessage() {}
      close() {}
    });
    const {view, label} = setupOrdering();
    const healthy = currentHealth({spot_service_instance_id: undefined, spot_poll_seq: undefined});
    const failed = currentHealth({spot_service_instance_id: undefined, spot_poll_seq: undefined,
      spot_poll_status: 'timeout', spot_raw_validity: 'not_received', temperature_value_origin: 'none'});
    const requests: Array<{resolve: (health: HealthSnapshot) => void; reject: (error: Error) => void}> = [];
    apiClient.defaults.adapter = config => {
      expect(config.url).toBe('/health');
      expect(config.method).toBe('get');
      return new Promise((resolve, reject) => requests.push({
        resolve: health => resolve({data: health, status: 200, statusText: 'OK', headers: {}, config}), reject,
      }));
    };
    const send = (source: number, sequence = 1, health = healthy, transport: 'bc' | 'storage' = 'storage') => {
      const payload = {tab_id: 'leader-a', kind: 'health', source_id: `capacity-source-${source}`,
        health_sequence: sequence, sent_at: Date.now(), data: health};
      if (transport === 'bc') channels.at(-1)?.onmessage?.({data: payload});
      else window.dispatchEvent(new StorageEvent('storage', {
        key: 'dashboard_system_broadcast_v1', newValue: JSON.stringify(payload),
      }));
    };
    const fill = async () => {
      await act(async () => {for (let source = 0; source < 256; source++) send(source); send(255, 2, failed);});
      expect(label()).toBe('SPOT DOWN');
      expect(requests).toHaveLength(0);
    };
    return {view, label, healthy, failed, requests, send, fill, maps, history: () => maps.values().next().value!};
  };

  it.each(['legacy', 'identified'] as const)('I2a confirms a higher sequence arriving after request start for %s health', async identity => {
    const {view, label, healthy, requests, send, fill, history} = setupCapacityOrdering();
    const captured = identity === 'legacy' ? healthy : {...healthy, spot_temperature: {...healthy.spot_temperature,
      spot_service_instance_id: 'live-service', spot_poll_seq: 10}};
    const later = {...captured, spot_temperature: {...captured.spot_temperature,
      ...(identity === 'identified' ? {spot_poll_seq: 11} : {}), spot_poll_status: 'timeout' as const,
      spot_raw_validity: 'not_received' as const, temperature_value_origin: 'none' as const}};
    const key = JSON.stringify(['leader-a', 'capacity-source-256']);
    try {
      await fill();
      await act(async () => {send(256, 1, captured, 'storage'); send(256, 2, later, 'bc'); send(256, 1, captured, 'bc');});
      expect(requests).toHaveLength(1);
      await act(async () => {requests[0].resolve(captured);});
      expect(requests).toHaveLength(2);
      expect(history().get(key)).toBe(1);
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(256, 2, later, 'storage'); send(256, 2, later, 'bc');});
      expect(requests).toHaveLength(2);
      expect(history().get(key)).toBe(1);
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async () => {requests[1].resolve(later);});
      expect(label()).toBe('SPOT DOWN');
      expect(history().get(key)).toBe(2);
      const confirmedReceipt = latestVm.healthReceipt;
      await act(async () => {send(256, 2, later);});
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(confirmedReceipt);
      await act(async () => {send(256, 3, {...captured, spot_temperature: {...captured.spot_temperature,
        ...(identity === 'identified' ? {spot_poll_seq: 12} : {})}});});
      expect(label()).toBe('SPOT OK');
      expect(history().size).toBe(256);
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('R5a preserves completed CONFIG against delayed same-poll startup', async () => {
    const {view, send, label} = setupOrdering();
    const completed = currentHealth({spot_poll_seq: 1, spot_poll_status: 'config_missing',
      spot_raw_validity: 'not_received', temperature_value_origin: 'none'});
    completed.comm = {...completed.comm, spot: {read_failures: 2}};
    try {
      await act(async () => {send(completed);});
      expect(label()).toBe('SPOT CONFIG');
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(currentHealth({spot_poll_seq: 1, spot_poll_status: 'not_attempted',
        spot_snapshot_age_ms: null, spot_value_age_ms: null, spot_source_freshness: 'unknown'}));});
      expect(label()).toBe('SPOT CONFIG');
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(latestVm.health?.comm?.spot?.read_failures).toBe(2);
      await act(async () => {send(currentHealth({spot_poll_seq: 2}));});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('I2 capacity confirms an evicted legacy sender without reviving its old OK', async () => {
    const {view, label, healthy, failed, requests, send, fill, history} = setupCapacityOrdering();
    try {
      await fill();
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(256, 1, healthy, 'bc'); send(256, 1, healthy, 'storage');});
      expect(requests).toHaveLength(1);
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async () => {requests[0].resolve(failed);});
      expect(history().size).toBe(256);
      expect(history().has(JSON.stringify(['leader-a', 'capacity-source-0']))).toBe(false);
      const confirmedReceipt = latestVm.healthReceipt;
      await act(async () => {send(0, 1, healthy, 'storage'); send(0, 1, healthy, 'bc');});
      expect(requests).toHaveLength(2);
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(confirmedReceipt);
      await act(async () => {requests[1].resolve(failed); send(0, 1, healthy);});
      expect(requests).toHaveLength(2);
      expect(label()).toBe('SPOT DOWN');
      await act(async () => {send(0, 2, healthy);});
      expect(label()).toBe('SPOT OK');
      expect(history().size).toBe(256);
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('I2 capacity bounds queued senders, deduplicates confirmations and retries failure', async () => {
    const {view, label, healthy, failed, requests, send, fill, history, maps} = setupCapacityOrdering();
    try {
      await fill();
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(256, 1, healthy, 'bc'); send(256, 2, healthy, 'storage');});
      expect(requests).toHaveLength(1);
      await act(async () => {for (let source = 257; source < 801; source++) send(source);});
      expect(requests).toHaveLength(1);
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(receipt);
      maps.forEach(map => expect(map.size).toBeLessThanOrEqual(256));
      await act(async () => {requests[0].reject(new Error('Synthetic capacity confirmation failure'));});
      expect(requests).toHaveLength(2);
      expect(history().has(JSON.stringify(['leader-a', 'capacity-source-256']))).toBe(false);
      expect(latestVm.healthReceipt).toBe(receipt);
      await act(async () => {requests[1].resolve(failed);});
      expect(history().size).toBe(256);
      await act(async () => {send(800, 1, healthy);});
      expect(requests).toHaveLength(2);
      expect(label()).toBe('SPOT DOWN');
      await act(async () => {send(256, 2, healthy);});
      expect(requests).toHaveLength(3);
      await act(async () => {requests[2].resolve(healthy);});
      expect(label()).toBe('SPOT OK');
      expect(history().size).toBe(256);
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it.each(['hidden', 'reconnect', 'unmount'])('I2 capacity preserves the receipt when confirmation completes during %s', async condition => {
    const {view, label, healthy, requests, send, fill, history} = setupCapacityOrdering();
    let finishReconnect!: (value: {ok: boolean}) => void;
    let reconnect!: Promise<boolean>;
    vi.spyOn(systemService, 'reconnect').mockImplementation(() => new Promise(resolve => {finishReconnect = resolve;}));
    try {
      await fill();
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(256);});
      expect(requests).toHaveLength(1);
      await act(async () => {
        if (condition === 'hidden') {visibility = 'hidden'; document.dispatchEvent(new Event('visibilitychange'));}
        else if (condition === 'reconnect') reconnect = latestVm.reconnect();
        else view.unmount();
      });
      await act(async () => {requests[0].resolve(healthy);});
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(history().has(JSON.stringify(['leader-a', 'capacity-source-256']))).toBe(false);
      if (condition !== 'unmount') {
        expect(label()).toBe('SPOT DOWN');
        await act(async () => {send(256);});
        expect(requests).toHaveLength(1);
        await act(async () => {
          if (condition === 'hidden') {visibility = 'visible'; document.dispatchEvent(new Event('visibilitychange'));}
          else {finishReconnect({ok: true}); await reconnect;}
        });
        await act(async () => {send(256);});
        expect(requests).toHaveLength(2);
        await act(async () => {requests[1].resolve(healthy);});
        expect(label()).toBe('SPOT OK');
      }
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('I2 capacity cannot overwrite a newer direct request or register a superseded sender', async () => {
    const {view, label, healthy, failed, requests, send, fill, history} = setupCapacityOrdering();
    try {
      await fill();
      await act(async () => {send(256);});
      expect(requests).toHaveLength(1);
      let latest!: Promise<HealthSnapshot | null>;
      await act(async () => {latest = latestVm.fetchHealth();});
      await act(async () => {requests[1].resolve(failed); await latest;});
      const receipt = latestVm.healthReceipt;
      await act(async () => {requests[0].resolve(healthy);});
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(history().has(JSON.stringify(['leader-a', 'capacity-source-256']))).toBe(false);
      await act(async () => {send(256);});
      expect(requests).toHaveLength(3);
      await act(async () => {requests[2].resolve(healthy);});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it('I2 capacity bounds retired services and confirms an evicted predecessor', async () => {
    const {view, send, label} = setupOrdering();
    const retired: Array<Set<string>> = [];
    const setAdd = Set.prototype.add;
    vi.spyOn(Set.prototype, 'add').mockImplementation(function (this: Set<string>, value: string) {
      if (typeof value === 'string' && value.startsWith('capacity-service-') && !retired.length) retired.push(this);
      return setAdd.call(this, value);
    });
    let actual = currentHealth({spot_service_instance_id: 'capacity-service-0', spot_poll_seq: 1});
    let requests = 0;
    apiClient.defaults.adapter = async config => {requests++; return {data: actual, status: 200, statusText: 'OK', headers: {}, config};};
    try {
      for (let service = 0; service < 258; service++) {
        actual = currentHealth({spot_service_instance_id: `capacity-service-${service}`, spot_poll_seq: 1,
          spot_poll_status: service === 257 ? 'timeout' : 'success'});
        await act(async () => {await latestVm.fetchHealth();});
      }
      expect(label()).toBe('SPOT DOWN');
      expect(retired[0].size).toBe(256);
      expect(retired[0].has('capacity-service-0')).toBe(false);
      expect(retired[0].has('capacity-service-257')).toBe(false);
      await act(async () => {send(currentHealth({spot_service_instance_id: 'capacity-service-0', spot_poll_seq: 1}));});
      expect(requests).toBe(259);
      expect(label()).toBe('SPOT DOWN');
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('capacity-service-257');
      await act(async () => {send(currentHealth({spot_service_instance_id: 'capacity-service-0', spot_poll_seq: 2}));});
      expect(requests).toBe(259);
      actual = currentHealth({spot_service_instance_id: 'capacity-service-258', spot_poll_seq: 0,
        spot_poll_status: 'not_attempted', spot_raw_validity: 'not_received', spot_source_freshness: 'unknown',
        temperature_value_origin: 'none', spot_snapshot_age_ms: null});
      await act(async () => {await latestVm.fetchHealth();});
      expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('capacity-service-258');
      expect(retired[0].size).toBe(256);
      expect(retired[0].has('capacity-service-258')).toBe(false);
      actual = currentHealth({spot_service_instance_id: 'capacity-service-258', spot_poll_seq: 1});
      await act(async () => {send(actual);});
      expect(label()).toBe('SPOT OK');
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });

  it.each(['hidden', 'reconnect', 'unmount'] as const)('I2 capacity preserves retired-service confirmation receipt during %s', async condition => {
    const {view, send, label} = setupOrdering();
    let actual = currentHealth({spot_service_instance_id: 'capacity-service-0', spot_poll_seq: 1});
    apiClient.defaults.adapter = async config => ({data: actual, status: 200, statusText: 'OK', headers: {}, config});
    let finishReconnect!: () => void;
    vi.spyOn(systemService, 'reconnect').mockImplementation(() => new Promise(resolve => {
      finishReconnect = () => resolve({ok: true});
    }));
    try {
      for (let service = 0; service < 258; service++) {
        actual = currentHealth({spot_service_instance_id: `capacity-service-${service}`, spot_poll_seq: 1,
          spot_poll_status: service === 257 ? 'timeout' : 'success'});
        await act(async () => {await latestVm.fetchHealth();});
      }
      const requests: Array<(data: HealthSnapshot) => void> = [];
      apiClient.defaults.adapter = config => new Promise(resolve => {
        requests.push(data => resolve({data, status: 200, statusText: 'OK', headers: {}, config}));
      });
      const receipt = latestVm.healthReceipt;
      await act(async () => {send(currentHealth({spot_service_instance_id: 'capacity-service-0', spot_poll_seq: 1}));});
      expect(requests).toHaveLength(1);
      await act(async () => {
        if (condition === 'hidden') {visibility = 'hidden'; document.dispatchEvent(new Event('visibilitychange'));}
        if (condition === 'reconnect') void latestVm.reconnect();
        if (condition === 'unmount') view.unmount();
      });
      const recovered = currentHealth({spot_service_instance_id: 'capacity-service-257', spot_poll_seq: 2});
      await act(async () => {requests[0](recovered);});
      expect(latestVm.healthReceipt).toBe(receipt);
      expect(latestVm.health?.spot_temperature?.spot_poll_seq).toBe(1);
      if (condition !== 'unmount') {
        expect(label()).toBe('SPOT DOWN');
        await act(async () => {
          if (condition === 'hidden') {visibility = 'visible'; document.dispatchEvent(new Event('visibilitychange'));}
          else finishReconnect();
        });
        await act(async () => {send(currentHealth({spot_service_instance_id: 'capacity-service-0', spot_poll_seq: 2}));});
        expect(requests).toHaveLength(2);
        await act(async () => {requests[1](recovered);});
        expect(label()).toBe('SPOT OK');
      }
      expect(externalNetworkAttempts).toBe(0);
    } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
  });
});
