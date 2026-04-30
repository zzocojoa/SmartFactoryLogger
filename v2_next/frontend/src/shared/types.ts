import type { WidgetType } from '../scenes/DashboardSceneModel';
export type { WidgetType };

export interface FactoryData {
    // System
    Time: string;
    Status: string;
    
    // KPIs
    Speed: number | null;
    Press: number | null;
    Count: number | null;
    EndPos: number | null;
    Billet_Length: number | null;
    Die_ID?: string | null;
    Billet_Cycle_ID?: string | null;
    
    // Temperatures
    Spot: number | null;
    Temp_F: number | null;
    Temp_B: number | null;
    Billet_Temp: number | null;
    
    // Molds
    Mold1: number | null;
    Mold2: number | null;
    Mold3: number | null;
    Mold4: number | null;
    Mold5: number | null;
    Mold6: number | null;
    
    // Environment
    At_Temp: number | null;
    At_Pre: number | null;

    // Computed status (backend-derived)
    Computed?: ComputedStatus;
}

export interface ThresholdHits {
    speed: boolean;
    press: boolean;
    spot: boolean;
    temp_f: boolean;
    temp_b: boolean;
    billet: boolean;
    billet_temp: boolean;
    at_temp: boolean;
    at_pre: boolean;
    count: boolean;
    endpos: boolean;
}

export interface ComputedStatus {
    speed_level?: string;
    press_level?: string;
    spot_level?: string;
    spot_warning?: boolean;
    env_temp_level?: string;
    env_pre_level?: string;
    mold_levels?: Record<string, string>;
    jam_level?: string;
    thresholds?: ThresholdHits;
}

export interface SpotConfig {
    image_url: string;
    refresh_interval: number;
    crosshair_x: number;
    crosshair_y: number;
    crosshair_color: string;
    crosshair_thickness: number;
    crosshair_size: number;
    crosshair_gap: number;
    widget_width: number;
    widget_height: number;
    focus_step: number;
    focus_enabled: boolean;
}

export interface HealthSnapshot {
  running: boolean;
  thread_alive: boolean;
  driver_thread_alive?: boolean;
  last_update: number | null;
  driver_connected: boolean;
  mode: string;
  driver_snapshot_at?: number | null;
  driver_snapshot_age_sec?: number | null;
  driver_last_error?: string | null;
  app_version?: string;
  runtime_kind?: string;
  executable_path?: string;
  executable_mtime?: string | null;
  comm?: CommMetrics;
}

export interface CommChannelMetrics {
  connected?: boolean;
  connect_attempts?: number;
  connect_failures?: number;
  read_failures?: number;
  invalid_responses?: number;
  skipped_reads?: number;
  backoff_count?: number;
  backoff_sec?: number;
  next_retry_at?: number;
  last_error?: string | null;
  last_error_time?: number | null;
  last_success_time?: number | null;
  last_recovery_sec?: number | null;
  recovery_count?: number;
  total_downtime_sec?: number;
  current_downtime_sec?: number;
  last_disconnect_time?: number | null;
  last_recovery_at?: number | null;
  merge_blocks?: boolean;
  merge_failures?: number;
}

export interface CommSpotMetrics {
  last_value?: number | null;
  read_failures?: number;
  last_error_time?: number | null;
  last_success_time?: number | null;
  timeout_sec?: number;
}

export interface CommMetrics {
  extruder?: CommChannelMetrics;
  ls_plc?: CommChannelMetrics;
  spot?: CommSpotMetrics;
}

export interface CentralSyncResult {
  status: string;
  message: string;
  version: string | null;
  at?: number | null;
}

export interface CentralStatus {
  configured: boolean;
  running: boolean;
  server: string | null;
  device_id: string | null;
  backoff_sec: number;
  last_result: CentralSyncResult;
  meta?: ConfigSnapshot['meta'];
}

export interface CommLogInfo {
  path: string | null;
}

export interface StatsSnapshot {
  uptime_sec: number;
  total_requests: number;
  avg_latency_ms: number | null;
  error_count: number;
  total_http_error_count?: number;
  total_http_4xx_count?: number;
  total_http_5xx_count?: number;
  last: {
    latency_ms: number | null;
    path: string | null;
    status: number | null;
    timestamp: number | null;
  };
  window?: {
    window_sec: number;
    request_count: number;
    error_count: number;
    http_error_count?: number;
    http_4xx_count?: number;
    http_5xx_count?: number;
    error_rate: number | null;
    avg_latency_ms: number | null;
    p95_latency_ms: number | null;
    requests_per_sec?: number;
    top_paths?: Array<{
      path: string;
      count: number;
      error_rate: number | null;
      avg_latency_ms: number | null;
    }>;
  };
  errors?: {
    queue_size: number;
    last_error_at?: number | null;
    last_error_source?: string | null;
    last_error_message?: string | null;
    last_error_repeat?: number | null;
    source_counts?: Record<string, number>;
  };
  polling?: {
    window_sec: number;
    paths: Record<string, {
      count: number;
      requests_per_sec: number;
      avg_latency_ms?: number | null;
      error_rate?: number | null;
      unique_clients: number;
      top_clients: Array<{
        client: string;
        count: number;
      }>;
      success_count?: number;
      failure_count?: number;
      stale_count?: number;
      avg_age_sec?: number | null;
    }>;
  };
}

export interface ObservabilityErrorItem {
  time: number;
  time_iso?: string;
  source: string;
  message: string;
  detail?: string | null;
  path?: string | null;
  level?: string | null;
  repeat?: number;
}

export interface ObservabilityErrorsResponse {
  items: ObservabilityErrorItem[];
  summary: {
    queue_size: number;
    last_error_at?: number | null;
    last_error_source?: string | null;
    last_error_message?: string | null;
    last_error_repeat?: number | null;
    source_counts?: Record<string, number>;
  };
}

export interface MemoryCollectorItem {
  name: string;
  kind: string;
  exactness: 'exact' | 'estimated' | string;
  bytes: number;
  items?: number | null;
  note?: string | null;
}

export interface MemoryCollectorDeltaItem {
  name: string;
  kind: string;
  exactness: 'exact' | 'estimated' | string;
  bytes: number;
  delta_bytes: number;
  share_ratio: number;
  items?: number | null;
  note?: string | null;
}

export interface MemoryAlertItem {
  key: string;
  severity: 'info' | 'warn' | 'error';
  title: string;
  detail: string;
}

export interface MemorySamplingInfo {
  sample_interval_sec: number;
  history_limit: number;
  collector_history_limit: number;
  detail_refresh_interval_sec?: number;
}

export interface BackendMemorySample {
  captured_at: number;
  captured_at_iso: string;
  rss_bytes: number;
  vms_bytes: number;
  uss_bytes?: number | null;
  private_bytes?: number | null;
  thread_count: number;
  open_files_count?: number | null;
  handle_count?: number | null;
  gc_gen0: number;
  gc_gen1: number;
  gc_gen2: number;
}

export interface MemoryProfilerState {
  enabled: boolean;
  started_at?: string | null;
  last_snapshot_at?: string | null;
  last_diff_at?: string | null;
  already_running?: boolean;
  expires_at?: string | null;
  remaining_ttl_sec?: number | null;
  max_runtime_sec?: number | null;
}

export interface TracemallocDiffItem {
  trace: string;
  size_diff_bytes: number;
  size_bytes: number;
  count_diff: number;
  count: number;
}

export interface MemoryStateResponse {
  summary: BackendMemorySample;
  history: BackendMemorySample[];
  profiler: MemoryProfilerState;
  sampling: MemorySamplingInfo;
}

export interface MemoryDetailsResponse {
  backend_top_consumers: MemoryCollectorItem[];
  backend_growth: MemoryCollectorDeltaItem[];
  collector_history: Array<{
    captured_at: number;
    items: MemoryCollectorItem[];
  }>;
  latest_tracemalloc_diff: TracemallocDiffItem[];
}

export interface MemoryTabLeaderState {
  tab_id: string;
  mode: 'leader' | 'follower' | 'recovering' | 'standalone';
  leader_tab_id: string | null;
  last_broadcast_at: number | null;
}

export interface DashboardLeaderState {
  tab_id: string;
  mode: 'leader' | 'follower' | 'recovering' | 'standalone';
  leader_tab_id: string | null;
  last_broadcast_at: number | null;
}

export interface MemoryActionState {
  refresh: boolean;
  snapshot: boolean;
  profiler_action: 'start' | 'stop' | null;
  export: boolean;
}

export interface FrontendMemorySupport {
  mode: 'uasm' | 'performance-memory' | 'unsupported';
  supported: boolean;
  used_bytes?: number | null;
  total_bytes?: number | null;
  limit_bytes?: number | null;
  breakdown?: Array<{
    name: string;
    bytes: number;
  }>;
}

export interface FrontendMemorySnapshot {
  captured_at: number;
  support: FrontendMemorySupport;
  top_consumers: MemoryCollectorItem[];
  growth: MemoryCollectorDeltaItem[];
  alerts: MemoryAlertItem[];
  last_refresh_at: number;
  last_export_at?: number | null;
  last_summary_at?: number | null;
  last_details_at?: number | null;
  last_export_meta_at?: number | null;
  summary_request_count?: number;
  details_request_count?: number;
  last_summary_reason?: string | null;
  refresh_error?: string | null;
  history: Array<{
    captured_at: number;
    app_bytes: number;
    heap_used_bytes?: number | null;
    heap_total_bytes?: number | null;
  }>;
}

export interface SpotPollingDiagnostics {
  in_flight: boolean;
  refresh_interval_ms: number | null;
  fetch_count: number;
  error_count: number;
  last_fetch_started_at: number | null;
  last_fetch_completed_at: number | null;
  last_fetch_latency_ms: number | null;
  next_fetch_scheduled_at: number | null;
  last_fetch_reason: string | null;
}

export interface FrontendErrorEntry {
  time: number;
  type: 'error' | 'unhandledrejection';
  message: string;
  detail?: string;
  stack?: string;
}

export type NotificationLevel = 'info' | 'warn' | 'error';
export type NotificationLifecycle = 'active' | 'resolved' | 'history';

export interface NotificationPushOptions {
  groupKey?: string;
  lifecycle?: NotificationLifecycle;
  detail?: string;
}

export interface NotificationItem {
  id: string;
  time: number;
  title: string;
  message: string;
  level: NotificationLevel;
  groupKey?: string;
  lifecycle?: NotificationLifecycle;
  detail?: string;
  resolvedAt?: number;
}

export interface ConfigSnapshot {
  config_path: string;
  encoding: string | null;
  config_writable?: boolean;
  restart_required: boolean;
  pending?: {
    path?: string;
    created_at?: string;
    source?: string;
    reason?: string;
  } | null;
  apply?: {
    applied?: string[];
    pending?: string[];
  };
  meta?: {
    device_id?: string | null;
    version?: string | null;
    last_sync?: string | null;
    source?: string | null;
    override_enabled?: boolean;
    override_by?: string | null;
    override_at?: string | null;
  };
  values: {
    extruder: { ip: string; port: number };
    ls_plc: { ip: string; port: number };
    spot: { ip: string; refresh_interval: number };
    thresholds?: {
      values?: {
        speed?: string;
        press?: string;
        spot?: string;
        temp_f?: string;
        temp_b?: string;
        billet?: string;
        billet_temp?: string;
        at_temp?: string;
        at_pre?: string;
        count?: string;
        endpos?: string;
      };
      enable?: {
        master_on?: boolean;
        speed?: boolean;
        press?: boolean;
        spot?: boolean;
        temp_f?: boolean;
        temp_b?: boolean;
        billet?: boolean;
        billet_temp?: boolean;
        at_temp?: boolean;
        at_pre?: boolean;
        count?: boolean;
        endpos?: boolean;
      };
    };
    settings: {
      logpath: string;
      snapshotpath: string;
      autosave: boolean;
      password_set: boolean;
    };
    logging: {
      rotation_enabled?: boolean;
      rotation_mode: string;
      cycle_idle_time: number;
      cycle_threshold_press: number;
    };
    system?: {
      interval_sec?: number;
      status_warn_ms?: number;
      status_offline_ms?: number;
    };
    mes?: {
      enabled: boolean;
      userid: string;
      password_set: boolean;
      starthour: number;
      endhour: number;
    };
  };
}

export interface SettingsFormState {
  extruderIp: string;
  extruderPort: string;
  lsIp: string;
  lsPort: string;
  spotIp: string;
  spotRefreshInterval: string;
  thresholdMasterOn: boolean;
  thresholdSpeedEnabled: boolean;
  thresholdSpeedValue: string;
  thresholdPressEnabled: boolean;
  thresholdPressValue: string;
  thresholdSpotEnabled: boolean;
  thresholdSpotValue: string;
  thresholdTempFEnabled: boolean;
  thresholdTempFValue: string;
  thresholdTempBEnabled: boolean;
  thresholdTempBValue: string;
  thresholdBilletEnabled: boolean;
  thresholdBilletValue: string;
  thresholdBilletTempEnabled: boolean;
  thresholdBilletTempValue: string;
  thresholdAtTempEnabled: boolean;
  thresholdAtTempValue: string;
  thresholdAtPreEnabled: boolean;
  thresholdAtPreValue: string;
  thresholdCountEnabled: boolean;
  thresholdCountValue: string;
  thresholdEndPosEnabled: boolean;
  thresholdEndPosValue: string;
  logPath: string;
  snapshotPath: string;
  autoSave: boolean;
  rotationEnabled: boolean;
  rotationMode: string;
  cycleIdleTime: string;
  cycleThresholdPress: string;
  intervalSec: string;
  statusWarnMs: string;
  statusOfflineMs: string;
  password: string;
  passwordSet: boolean;
  mesEnabled: boolean;
  mesUserId: string;
  mesPassword: string;
  mesPasswordSet: boolean;
  mesStartHour: string;
  mesEndHour: string;
}

export interface ConfigApplyResult {
  applied?: string[];
  pending?: string[];
}

export interface ConfigUpdateResponse {
  ok: boolean;
  restart_required: boolean;
  apply?: ConfigApplyResult;
  meta?: any;
  config?: any;
}

export type ThresholdKey =
  | 'speed'
  | 'press'
  | 'spot'
  | 'temp_f'
  | 'temp_b'
  | 'billet'
  | 'billet_temp'
  | 'at_temp'
  | 'at_pre'
  | 'count'
  | 'endpos';

export interface ThresholdEntry {
  enabled: boolean;
  value: number | null;
}

export interface ThresholdState {
  masterOn: boolean;
  entries: Record<ThresholdKey, ThresholdEntry>;
}

export type ConnectionTargetKey = 'extruder' | 'ls_plc' | 'spot';

export interface ThresholdItem {
  key: ThresholdKey;
  label: string;
  unit: string;
  enableField: keyof SettingsFormState;
  valueField: keyof SettingsFormState;
}

export interface ConnectionTestResult {
  ok: boolean;
  latency_ms: number | null;
  message: string;
  tested_at: number;
}

export type ConnectionTestState = Partial<Record<ConnectionTargetKey, ConnectionTestResult>>;

export interface ConnectionTestResponse {
  results: Record<string, { ok: boolean; latency_ms?: number; message?: string }>;
}

export interface PathHealthResult {
  status: 'OK' | 'WARN' | 'ERROR' | 'UNKNOWN';
  exists: boolean;
  writable: boolean;
  is_dir: boolean;
  is_network: boolean;
  latency_ms: number | null;
  message: string;
  checked_at: number;
}

export type PathHealthState = Partial<Record<'log' | 'snapshot', PathHealthResult>>;

export interface LayoutEntry {
  x: number;
  y: number;
  width: number;
  height: number;
  type?: WidgetType;
  title?: string;
  properties?: any;
}

export type LayoutMap = Record<string, LayoutEntry>;

export interface LayoutSnapshot {
  layout: LayoutMap;
  cols?: string | number | null;
  version?: string | null;
  updated_at?: string | null;
}

export interface LayoutSlotSummary {
  id: string;
  name: string;
  updated_at?: string | null;
  cols?: string | number | null;
}

export interface LayoutSlotsResponse {
  active_id?: string | null;
  slots: LayoutSlotSummary[];
}

