import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import axios from 'axios';
import { FactoryData, SpotConfig } from './types';
import './App.css';
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { DASHBOARD_LAYOUT_KEYS, getDashboardScene } from './scenes/DashboardScene';
import { SceneGridItemLike, SceneGridLayout } from '@grafana/scenes';
import {
  APP_TITLE,
  NOTICE_BODY_PREFIX,
  NOTICE_BODY_SUFFIX,
  NOTICE_FOOTER,
  NOTICE_TEMP_THRESHOLD,
  NOTICE_TITLE,
  SPOT_UNIT,
} from './constants/uiText';

if (typeof window !== 'undefined') {
  // Ensure Grafana runtime is ready before Scenes are created.
  initScenesRuntime();
}

const API_BASE = 'http://localhost:8000';

const SPOT_WARN_TEMP = 580;
const SPOT_NORMAL_MIN = 480;
const SPOT_HIGH_MIN = 540;
const SPOT_MAX_TEMP = 600;
const SPARKLINE_POINTS = 10;
const LAYOUT_STORAGE_KEY = 'grafana_scene_layout_v1';
const LAYOUT_COLS_KEY = 'grafana_scene_layout_cols';
const LAYOUT_BACKUP_KEY = 'grafana_scene_layout_v1_backup';
const LEGACY_LAYOUT_COLS = 24;
const CURRENT_LAYOUT_COLS = 60;
const SPEED_MAX = 8;
const PRESS_MAX = 180;
const PRESS_RUNNING_THRESHOLD = 20;
const ALERT_HOLD_MS = 2000;
const ALERT_HOLD_LONG_MS = 5000;
const STATUS_WARN_MS = 2000;
const STATUS_OFFLINE_MS = 5000;
const SETTINGS_AUTO_REFRESH_MS = 4000;

const APPLY_KEY_LABELS: Record<string, string> = {
  'settings.logpath': '로그 경로',
  'settings.snapshotpath': '스냅샷 경로',
  'settings.autosave': '자동 저장',
  'settings.password_set': '비밀번호 설정',
  'logging.rotation_enabled': '로그 회전 사용',
  'logging.rotation_mode': '회전 모드',
  'logging.cycle_idle_time': '사이클 유휴 시간',
  'logging.cycle_threshold_press': '사이클 압력 임계값',
  'logging.csv_header': 'CSV 헤더',
  'system.intervalsec': '수집 주기',
  'spot.ip': 'SPOT IP',
  'spot.url': 'SPOT URL',
  'spot.image_url': 'SPOT 이미지 URL',
  'spot.refresh_interval': 'SPOT 갱신 주기',
  'spot.crosshair_x': 'SPOT 크로스헤어 X',
  'spot.crosshair_y': 'SPOT 크로스헤어 Y',
  'spot.crosshair_color': 'SPOT 크로스헤어 색상',
  'spot.crosshair_thickness': 'SPOT 크로스헤어 두께',
  'spot.crosshair_size': 'SPOT 크로스헤어 크기',
  'spot.crosshair_gap': 'SPOT 크로스헤어 간격',
  'spot.focus_url': 'SPOT 포커스 URL',
  'spot.focus_step': 'SPOT 포커스 스텝',
  'spot.actuator_ip': 'SPOT 액추에이터 IP',
  'spot.actuator_step': 'SPOT 액추에이터 스텝',
  'spot.actuator_url': 'SPOT 액추에이터 URL',
  'spot.widget_width': 'SPOT 위젯 너비',
  'spot.widget_height': 'SPOT 위젯 높이',
  'extruder.ip': 'Extruder IP',
  'extruder.port': 'Extruder Port',
  'ls_plc.ip': 'LS PLC IP',
  'ls_plc.port': 'LS PLC Port',
  'ls_plc.targets': 'LS PLC 타깃 매핑',
  'thresholds.enable.master_on': '임계값 사용(마스터)',
  'thresholds.enable.speed': '임계값 사용(속도)',
  'thresholds.enable.press': '임계값 사용(압력)',
  'thresholds.enable.spot': '임계값 사용(SPOT)',
  'thresholds.enable.temp_f': '임계값 사용(온도 앞)',
  'thresholds.enable.temp_b': '임계값 사용(온도 뒤)',
  'thresholds.enable.billet': '임계값 사용(빌렛 길이)',
  'thresholds.enable.billet_temp': '임계값 사용(빌렛 온도)',
  'thresholds.enable.at_temp': '임계값 사용(환경 온도)',
  'thresholds.enable.at_pre': '임계값 사용(환경 습도)',
  'thresholds.enable.count': '임계값 사용(카운트)',
  'thresholds.enable.endpos': '임계값 사용(종료 위치)',
  'thresholds.values.speed': '임계값 값(속도)',
  'thresholds.values.press': '임계값 값(압력)',
  'thresholds.values.spot': '임계값 값(SPOT)',
  'thresholds.values.temp_f': '임계값 값(온도 앞)',
  'thresholds.values.temp_b': '임계값 값(온도 뒤)',
  'thresholds.values.billet': '임계값 값(빌렛 길이)',
  'thresholds.values.billet_temp': '임계값 값(빌렛 온도)',
  'thresholds.values.at_temp': '임계값 값(환경 온도)',
  'thresholds.values.at_pre': '임계값 값(환경 습도)',
  'thresholds.values.count': '임계값 값(카운트)',
  'thresholds.values.endpos': '임계값 값(종료 위치)',
};

type HealthSnapshot = {
  running: boolean;
  thread_alive: boolean;
  last_update: number | null;
  driver_connected: boolean;
  mode: string;
  comm?: CommMetrics;
};

type CommChannelMetrics = {
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
  merge_blocks?: boolean;
  merge_failures?: number;
};

type CommSpotMetrics = {
  last_value?: number | null;
  read_failures?: number;
  last_error_time?: number | null;
  last_success_time?: number | null;
  timeout_sec?: number;
};

type CommMetrics = {
  extruder?: CommChannelMetrics;
  ls_plc?: CommChannelMetrics;
  spot?: CommSpotMetrics;
};

type CentralSyncResult = {
  status: string;
  message: string;
  version: string | null;
  at?: number | null;
};

type CentralStatus = {
  configured: boolean;
  running: boolean;
  server: string | null;
  device_id: string | null;
  backoff_sec: number;
  last_result: CentralSyncResult;
  meta?: ConfigSnapshot['meta'];
};

type CommLogInfo = {
  path: string | null;
};

type StatsSnapshot = {
  uptime_sec: number;
  total_requests: number;
  avg_latency_ms: number | null;
  error_count: number;
  last: {
    latency_ms: number | null;
    path: string | null;
    status: number | null;
    timestamp: number | null;
  };
};

type NotificationLevel = 'info' | 'warn' | 'error';

type NotificationItem = {
  id: string;
  time: number;
  title: string;
  message: string;
  level: NotificationLevel;
};

const MAX_NOTIFICATIONS = 50;

type ConfigSnapshot = {
  config_path: string;
  encoding: string | null;
  config_writable?: boolean;
  restart_required: boolean;
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
  };
};

type SettingsFormState = {
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
  password: string;
  passwordSet: boolean;
};

type ConfigApplyResult = {
  applied?: string[];
  pending?: string[];
};

type ConfigUpdateResponse = {
  ok: boolean;
  restart_required: boolean;
  apply?: ConfigApplyResult;
};

type ThresholdKey =
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

type ThresholdEntry = {
  enabled: boolean;
  value: number | null;
};

type ThresholdState = {
  masterOn: boolean;
  entries: Record<ThresholdKey, ThresholdEntry>;
};

type ConnectionTargetKey = 'extruder' | 'ls_plc' | 'spot';

type ThresholdItem = {
  key: ThresholdKey;
  label: string;
  unit: string;
  enableField: keyof SettingsFormState;
  valueField: keyof SettingsFormState;
};

type ConnectionTestResult = {
  ok: boolean;
  latency_ms: number | null;
  message: string;
  tested_at: number;
};

type ConnectionTestState = Partial<Record<ConnectionTargetKey, ConnectionTestResult>>;

type ConnectionTestResponse = {
  results: Record<string, { ok: boolean; latency_ms?: number; message?: string }>;
};

type PathHealthResult = {
  status: 'OK' | 'WARN' | 'ERROR' | 'UNKNOWN';
  exists: boolean;
  writable: boolean;
  is_dir: boolean;
  is_network: boolean;
  latency_ms: number | null;
  message: string;
  checked_at: number;
};

type PathHealthState = Partial<Record<'log' | 'snapshot', PathHealthResult>>;

type LayoutEntry = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type LayoutMap = Record<string, LayoutEntry>;

type LayoutSnapshot = {
  layout: LayoutMap;
  cols?: string | number | null;
  version?: string | null;
  updated_at?: string | null;
};

type LayoutSlotSummary = {
  id: string;
  name: string;
  updated_at?: string | null;
  cols?: string | number | null;
};

type LayoutSlotsResponse = {
  active_id?: string | null;
  slots: LayoutSlotSummary[];
};

const coerceLayoutEntry = (entry: unknown): LayoutEntry | null => {
  if (!entry || typeof entry !== 'object') {
    return null;
  }
  const raw = entry as Record<string, unknown>;
  const width = raw.width ?? raw.w;
  const height = raw.height ?? raw.h;
  const x = Number(raw.x);
  const y = Number(raw.y);
  const w = Number(width);
  const h = Number(height);
  if (![x, y, w, h].every((value) => Number.isFinite(value))) {
    return null;
  }
  return { x, y, width: w, height: h };
};

const buildLayoutMapFromArray = (items: unknown[]): LayoutMap => {
  const layout: LayoutMap = {};
  DASHBOARD_LAYOUT_KEYS.forEach((key, index) => {
    const entry = coerceLayoutEntry(items[index]);
    if (entry) {
      layout[key] = entry;
    }
  });
  return layout;
};

const buildLayoutMapFromObject = (value: Record<string, unknown>): LayoutMap => {
  const layout: LayoutMap = {};
  Object.entries(value).forEach(([key, entry]) => {
    const parsed = coerceLayoutEntry(entry);
    if (parsed) {
      layout[key] = parsed;
    }
  });
  return layout;
};

const getLayoutMaxExtent = (layout: LayoutMap): number => {
  let maxExtent = 0;
  Object.values(layout).forEach((item) => {
    const x = item.x ?? 0;
    const width = item.width ?? 0;
    if (x + width > maxExtent) {
      maxExtent = x + width;
    }
  });
  return maxExtent;
};

const scaleLayoutMap = (layout: LayoutMap, scale: number): LayoutMap => {
  const scaled: LayoutMap = {};
  Object.entries(layout).forEach(([key, item]) => {
    scaled[key] = {
      ...item,
      x: Math.max(0, Math.round(item.x * scale)),
      width: Math.max(1, Math.round(item.width * scale)),
    };
  });
  return scaled;
};

const normalizeLayoutMap = (layout: LayoutMap, colsValue?: string | number | null) => {
  const savedCols =
    colsValue === undefined || colsValue === null || `${colsValue}`.trim() === ''
      ? Number.NaN
      : Number(colsValue);
  const maxExtent = getLayoutMaxExtent(layout);
  const isLegacy = maxExtent > 0 && maxExtent <= LEGACY_LAYOUT_COLS;
  if (savedCols === LEGACY_LAYOUT_COLS || (!Number.isFinite(savedCols) && isLegacy)) {
    return {
      layout: scaleLayoutMap(layout, CURRENT_LAYOUT_COLS / LEGACY_LAYOUT_COLS),
      cols: CURRENT_LAYOUT_COLS,
      scaled: true,
    };
  }
  return {
    layout,
    cols: Number.isFinite(savedCols) ? savedCols : CURRENT_LAYOUT_COLS,
    scaled: false,
  };
};

const buildLayoutMap = (children: SceneGridItemLike[]): LayoutMap => {
  const next: LayoutMap = {};
  children.forEach((child) => {
    const key = child.state.key;
    const { x, y, width, height } = child.state;
    if (!key || x === undefined || y === undefined || width === undefined || height === undefined) {
      return;
    }
    next[key] = { x, y, width, height };
  });
  return next;
};

const clampNumber = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const buildSparklinePaths = (
  values: number[],
  width: number,
  height: number,
  thresholds: number[] = [],
  domain?: { min?: number; max?: number }
) => {
  if (values.length === 0) {
    return {
      linePath: '',
      areaPath: '',
      points: [] as Array<{ x: number; y: number }>,
      thresholdLines: [] as Array<{ y: number; value: number }>,
    };
  }
  const min = Number.isFinite(domain?.min)
    ? Math.min(domain?.min as number, ...values)
    : Math.min(...values);
  const max = Number.isFinite(domain?.max)
    ? Math.max(domain?.max as number, ...values)
    : Math.max(...values);
  const range = Math.max(max - min, 1);
  const lastIndex = Math.max(values.length - 1, 1);
  const points = values.map((value, index) => {
    const x = (index / lastIndex) * width;
    const y = height - ((value - min) / range) * height;
    return { x, y };
  });
  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(' ');
  const areaPath = `${linePath} L${width.toFixed(2)},${height.toFixed(2)} L0,${height.toFixed(2)} Z`;
  const thresholdLines = thresholds
    .filter((value) => Number.isFinite(value))
    .map((value) => {
      const clamped = clampNumber(value, min, max);
      const y = height - ((clamped - min) / range) * height;
      return { y, value };
    });
  return { linePath, areaPath, points, thresholdLines };
};

const useLastValidNumber = (value: number | null | undefined) => {
  const lastRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      lastRef.current = value;
    }
  }, [value]);

  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return lastRef.current;
};

const useSustainedFlag = (condition: boolean, durationMs: number) => {
  const [active, setActive] = useState(false);
  const sinceRef = useRef<number | null>(null);

  useEffect(() => {
    const now = Date.now();
    if (condition) {
      if (sinceRef.current === null) {
        sinceRef.current = now;
      }
      if (!active && now - sinceRef.current >= durationMs) {
        setActive(true);
      }
    } else {
      sinceRef.current = null;
      if (active) {
        setActive(false);
      }
    }
  }, [condition, durationMs, active]);

  return active;
};

type ThresholdLevel = 'normal' | 'warn' | 'danger';

const useThresholdLevel = (value: number, warnThreshold: number, dangerThreshold: number, holdMs: number) => {
  const [level, setLevel] = useState<ThresholdLevel>('normal');
  const warnSinceRef = useRef<number | null>(null);
  const dangerSinceRef = useRef<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(value)) {
      warnSinceRef.current = null;
      dangerSinceRef.current = null;
      return;
    }

    const now = Date.now();

    if (value >= dangerThreshold) {
      if (dangerSinceRef.current === null) {
        dangerSinceRef.current = now;
      }
      warnSinceRef.current = null;
      if (now - dangerSinceRef.current >= holdMs && level !== 'danger') {
        setLevel('danger');
      }
      return;
    }

    dangerSinceRef.current = null;

    if (value >= warnThreshold) {
      if (warnSinceRef.current === null) {
        warnSinceRef.current = now;
      }
      if (level === 'danger') {
        setLevel('warn');
      }
      if (now - warnSinceRef.current >= holdMs && level !== 'warn') {
        setLevel('warn');
      }
      return;
    }

    warnSinceRef.current = null;
    if (level !== 'normal') {
      setLevel('normal');
    }
  }, [value, warnThreshold, dangerThreshold, holdMs, level]);

  return level;
};

const formatTime = (timestamp: number | null) => {
  if (!timestamp) {
    return '--:--:--';
  }
  const date = new Date(timestamp);
  return date.toTimeString().slice(0, 8);
};

const formatTimeFromSec = (value?: number | null) => {
  if (!value) {
    return '--:--:--';
  }
  return formatTime(value * 1000);
};

const formatAgeSec = (value?: number | null, nowMs?: number | null) => {
  if (!value || !nowMs) {
    return '--';
  }
  const ageSec = Math.max(0, Math.round(nowMs / 1000 - value));
  return `${ageSec}s`;
};

const formatOptionalNumber = (value?: number | null, decimals: number = 0) => {
  if (value === undefined || value === null) {
    return '--';
  }
  return formatNumber(value, decimals);
};

const formatOptionalSeconds = (value?: number | null) => {
  if (value === undefined || value === null) {
    return '--';
  }
  return `${Math.round(value)}s`;
};

const formatOptionalText = (value?: string | null) => {
  const trimmed = (value ?? '').trim();
  return trimmed ? trimmed : '--';
};

const calcRecoverySec = (metrics?: {
  last_recovery_sec?: number | null;
  last_error_time?: number | null;
  last_success_time?: number | null;
}) => {
  if (!metrics) {
    return null;
  }
  if (metrics.last_recovery_sec !== undefined && metrics.last_recovery_sec !== null) {
    return metrics.last_recovery_sec;
  }
  const lastErr = metrics.last_error_time;
  const lastOk = metrics.last_success_time;
  if (lastErr && lastOk && lastOk > lastErr) {
    return lastOk - lastErr;
  }
  return null;
};

type CommBadge = {
  key: string;
  text: string;
  title: string;
  state: 'ok' | 'warn' | 'error' | 'idle';
};

const buildCommBadge = (
  key: string,
  metrics?: CommChannelMetrics,
  nowMs?: number | null
): CommBadge => {
  if (!metrics) {
    return { key, text: `${key} --`, title: `${key}: no data`, state: 'idle' };
  }
  const connected = Boolean(metrics.connected);
  const failures = (metrics.connect_failures ?? 0) + (metrics.read_failures ?? 0);
  const hasError = Boolean(metrics.last_error_time || failures > 0);
  const state: CommBadge['state'] = connected ? 'ok' : hasError ? 'error' : 'warn';
  const backoff = metrics.backoff_sec ?? 0;
  const mergeState = metrics.merge_blocks === undefined ? '' : `Merge ${metrics.merge_blocks ? 'ON' : 'OFF'}`;
  const titleParts = [
    `${key} ${connected ? '연결됨' : '끊김'}`,
    `실패 ${failures}`,
    `백오프 ${backoff}s`,
    `마지막 오류 ${formatTimeFromSec(metrics.last_error_time)}`,
    `오류 후 경과 ${formatAgeSec(metrics.last_error_time ?? null, nowMs ?? null)}`,
  ];
  if (metrics.last_recovery_sec !== null && metrics.last_recovery_sec !== undefined) {
    titleParts.push(`복구시간 ${Math.round(metrics.last_recovery_sec)}s`);
  }
  if (mergeState) {
    titleParts.push(mergeState);
  }
  if (metrics.last_error) {
    titleParts.push(`메시지 ${metrics.last_error}`);
  }
  return {
    key,
    text: `${key} ${connected ? 'OK' : 'DOWN'}`,
    title: titleParts.join(' | '),
    state,
  };
};

const buildSpotCommBadge = (
  key: string,
  metrics?: CommSpotMetrics,
  nowMs?: number | null,
  refreshMs?: number | null
): CommBadge => {
  if (!metrics) {
    return { key, text: `${key} --`, title: `${key}: no data`, state: 'idle' };
  }
  const lastSuccess = metrics.last_success_time ?? null;
  const lastError = metrics.last_error_time ?? null;
  const readFailures = metrics.read_failures ?? 0;
  const ageMs = lastSuccess && nowMs ? Math.max(0, nowMs - lastSuccess * 1000) : null;
  const staleMs = Math.max(2000, Math.round((refreshMs ?? 1000) * 3));
  let state: CommBadge['state'] = 'idle';
  let label = 'IDLE';
  if (lastSuccess && ageMs !== null && ageMs <= staleMs) {
    state = 'ok';
    label = 'OK';
  } else if (lastSuccess && ageMs !== null && ageMs > staleMs) {
    state = 'warn';
    label = 'STALE';
  } else if (lastError || readFailures > 0) {
    state = 'error';
    label = 'DOWN';
  } else {
    state = 'warn';
    label = 'WAIT';
  }
  const titleParts = [
    `${key} ${label}`,
    `최근 성공 ${formatTimeFromSec(lastSuccess)}`,
    `최근 오류 ${formatTimeFromSec(lastError)}`,
    `오류 후 경과 ${formatAgeSec(lastError, nowMs ?? null)}`,
    `실패 ${readFailures}`,
  ];
  return {
    key,
    text: `${key} ${label}`,
    title: titleParts.join(' | '),
    state,
  };
};

const formatNumber = (value: number, decimals: number) => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return value.toFixed(decimals);
};

const formatInteger = (value: number) => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return Math.round(value).toString();
};

const formatMetaTime = (value?: string | null) => {
  if (!value) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

const isValidIp = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }
  const parts = trimmed.split('.');
  if (parts.length !== 4) {
    return false;
  }
  return parts.every((part) => {
    if (!/^\d+$/.test(part)) {
      return false;
    }
    const num = Number(part);
    return num >= 0 && num <= 255;
  });
};

const isValidPort = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }
  if (!/^\d+$/.test(trimmed)) {
    return false;
  }
  const num = Number(trimmed);
  return num >= 1 && num <= 65535;
};

const isValidNumberInput = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return true;
  }
  const num = Number(trimmed);
  return Number.isFinite(num);
};

const parseThresholdValue = (value?: string | null) => {
  const trimmed = (value ?? '').trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const buildThresholdStateFromConfig = (thresholds?: ConfigSnapshot['values']['thresholds']): ThresholdState => {
  const enable = thresholds?.enable ?? {};
  const values = thresholds?.values ?? {};
  const buildEntry = (key: ThresholdKey): ThresholdEntry => ({
    enabled: Boolean(enable[key as keyof typeof enable]),
    value: parseThresholdValue(values[key as keyof typeof values]),
  });
  return {
    masterOn: Boolean(enable.master_on),
    entries: {
      speed: buildEntry('speed'),
      press: buildEntry('press'),
      spot: buildEntry('spot'),
      temp_f: buildEntry('temp_f'),
      temp_b: buildEntry('temp_b'),
      billet: buildEntry('billet'),
      billet_temp: buildEntry('billet_temp'),
      at_temp: buildEntry('at_temp'),
      at_pre: buildEntry('at_pre'),
      count: buildEntry('count'),
      endpos: buildEntry('endpos'),
    },
  };
};

const buildThresholdStateFromForm = (form: SettingsFormState): ThresholdState => ({
  masterOn: form.thresholdMasterOn,
  entries: {
    speed: { enabled: form.thresholdSpeedEnabled, value: parseThresholdValue(form.thresholdSpeedValue) },
    press: { enabled: form.thresholdPressEnabled, value: parseThresholdValue(form.thresholdPressValue) },
    spot: { enabled: form.thresholdSpotEnabled, value: parseThresholdValue(form.thresholdSpotValue) },
    temp_f: { enabled: form.thresholdTempFEnabled, value: parseThresholdValue(form.thresholdTempFValue) },
    temp_b: { enabled: form.thresholdTempBEnabled, value: parseThresholdValue(form.thresholdTempBValue) },
    billet: { enabled: form.thresholdBilletEnabled, value: parseThresholdValue(form.thresholdBilletValue) },
    billet_temp: { enabled: form.thresholdBilletTempEnabled, value: parseThresholdValue(form.thresholdBilletTempValue) },
    at_temp: { enabled: form.thresholdAtTempEnabled, value: parseThresholdValue(form.thresholdAtTempValue) },
    at_pre: { enabled: form.thresholdAtPreEnabled, value: parseThresholdValue(form.thresholdAtPreValue) },
    count: { enabled: form.thresholdCountEnabled, value: parseThresholdValue(form.thresholdCountValue) },
    endpos: { enabled: form.thresholdEndPosEnabled, value: parseThresholdValue(form.thresholdEndPosValue) },
  },
});

const isThresholdHit = (thresholds: ThresholdState, key: ThresholdKey, value: number | null | undefined) => {
  if (!thresholds.masterOn) {
    return false;
  }
  const entry = thresholds.entries[key];
  if (!entry?.enabled || entry.value === null) {
    return false;
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return false;
  }
  return value >= entry.value;
};

const THRESHOLD_LABELS: Record<ThresholdKey, string> = {
  speed: '속도',
  press: '압력',
  spot: 'SPOT',
  temp_f: '컨테이너 앞',
  temp_b: '컨테이너 뒤',
  billet: '빌렛 길이',
  billet_temp: '빌렛 온도',
  at_temp: '환경 온도',
  at_pre: '환경 습도',
  count: '카운트',
  endpos: '종료 위치',
};

const getSpeedState = (speed: number) => {
  if (speed >= 8) {
    return { label: '매우빠름', className: 'speed-very-fast' };
  }
  if (speed >= 6) {
    return { label: '빠름', className: 'speed-fast' };
  }
  if (speed >= 4) {
    return { label: '보통', className: 'speed-normal' };
  }
  if (speed >= 2) {
    return { label: '저속', className: 'speed-slow' };
  }
  return { label: '매우저속', className: 'speed-very-slow' };
};

const getPressState = (press: number) => {
  if (press >= 180) {
    return { label: '높음', className: 'press-high' };
  }
  if (press >= 126) {
    return { label: '보통', className: 'press-normal' };
  }
  return { label: '낮음', className: 'press-low' };
};

const SPEED_LEVEL_MAP: Record<string, { label: string; className: string }> = {
  very_fast: { label: '매우빠름', className: 'speed-very-fast' },
  fast: { label: '빠름', className: 'speed-fast' },
  normal: { label: '보통', className: 'speed-normal' },
  slow: { label: '저속', className: 'speed-slow' },
  very_slow: { label: '매우저속', className: 'speed-very-slow' },
};

const PRESS_LEVEL_MAP: Record<string, { label: string; className: string }> = {
  high: { label: '높음', className: 'press-high' },
  normal: { label: '보통', className: 'press-normal' },
  low: { label: '낮음', className: 'press-low' },
};

const mapSpeedLevel = (level?: string) => {
  if (!level) return null;
  return SPEED_LEVEL_MAP[level] ?? null;
};

const mapPressLevel = (level?: string) => {
  if (!level) return null;
  return PRESS_LEVEL_MAP[level] ?? null;
};

type SpotState = {
  label: string;
  statusClass: string;
  fillClass: string;
  warning: boolean;
  sparkClass: string;
};

const SPOT_LEVEL_MAP: Record<string, SpotState> = {
  low: {
    label: '저온',
    statusClass: 'spot-status-low',
    fillClass: 'spot-fill-low',
    warning: false,
    sparkClass: 'sparkline-low',
  },
  normal: {
    label: '보통',
    statusClass: 'spot-status-normal',
    fillClass: 'spot-fill-normal',
    warning: false,
    sparkClass: 'sparkline-normal',
  },
  high: {
    label: '고온',
    statusClass: 'spot-status-high',
    fillClass: 'spot-fill-high',
    warning: false,
    sparkClass: 'sparkline-high',
  },
  warning: {
    label: '경고',
    statusClass: 'spot-status-warning',
    fillClass: 'spot-fill-warning',
    warning: true,
    sparkClass: 'sparkline-warning',
  },
};

const mapSpotLevel = (level?: string) => {
  if (!level) return null;
  return SPOT_LEVEL_MAP[level] ?? null;
};

const getSpotState = (temp: number, warningActive: boolean): SpotState => {
  if (!Number.isFinite(temp)) {
    return {
      label: '저온',
      statusClass: 'spot-status-low',
      fillClass: 'spot-fill-low',
      warning: false,
      sparkClass: 'sparkline-low',
    };
  }
  if (temp >= SPOT_WARN_TEMP && warningActive) {
    return {
      label: '경고',
      statusClass: 'spot-status-warning',
      fillClass: 'spot-fill-warning',
      warning: true,
      sparkClass: 'sparkline-warning',
    };
  }
  if (temp >= SPOT_HIGH_MIN) {
    return {
      label: '고온',
      statusClass: 'spot-status-high',
      fillClass: 'spot-fill-high',
      warning: false,
      sparkClass: 'sparkline-high',
    };
  }
  if (temp >= SPOT_NORMAL_MIN) {
    return {
      label: '보통',
      statusClass: 'spot-status-normal',
      fillClass: 'spot-fill-normal',
      warning: false,
      sparkClass: 'sparkline-normal',
    };
  }
  return {
    label: '저온',
    statusClass: 'spot-status-low',
    fillClass: 'spot-fill-low',
    warning: false,
    sparkClass: 'sparkline-low',
  };
};

const getMoldState = (value: number) => {
  if (!Number.isFinite(value)) {
    return { className: 'mold-muted' };
  }
  return value >= 100 ? { className: 'mold-alert' } : { className: 'mold-normal' };
};

const MOLD_LEVEL_CLASS: Record<string, string> = {
  alert: 'mold-alert',
  normal: 'mold-normal',
  muted: 'mold-muted',
};

const mapMoldLevel = (level?: string) => {
  if (!level) return null;
  return MOLD_LEVEL_CLASS[level] ?? null;
};

const getEnvTempState = (value: number) => {
  if (!Number.isFinite(value)) {
    return { label: '미확인', className: 'env-muted' };
  }
  if (value >= 28) {
    return { label: '더움', className: 'env-hot' };
  }
  if (value < 10) {
    return { label: '추움', className: 'env-cold' };
  }
  return { label: '쾌적', className: 'env-comfort' };
};

const getEnvHumidityState = (value: number) => {
  if (!Number.isFinite(value)) {
    return { label: '미확인', className: 'env-muted' };
  }
  if (value >= 60) {
    return { label: '다습', className: 'env-humid' };
  }
  if (value < 30) {
    return { label: '건조', className: 'env-dry' };
  }
  return { label: '쾌적', className: 'env-comfort' };
};

const ENV_TEMP_LEVEL_MAP: Record<string, { label: string; className: string }> = {
  hot: { label: '더움', className: 'env-hot' },
  cold: { label: '추움', className: 'env-cold' },
  comfort: { label: '쾌적', className: 'env-comfort' },
  unknown: { label: '미확인', className: 'env-muted' },
};

const ENV_PRE_LEVEL_MAP: Record<string, { label: string; className: string }> = {
  humid: { label: '다습', className: 'env-humid' },
  dry: { label: '건조', className: 'env-dry' },
  comfort: { label: '쾌적', className: 'env-comfort' },
  unknown: { label: '미확인', className: 'env-muted' },
};

const mapEnvTempLevel = (level?: string) => {
  if (!level) return null;
  return ENV_TEMP_LEVEL_MAP[level] ?? null;
};

const mapEnvPreLevel = (level?: string) => {
  if (!level) return null;
  return ENV_PRE_LEVEL_MAP[level] ?? null;
};

const calcPercent = (value: number, max: number) => {
  if (!Number.isFinite(value) || max <= 0) {
    return 0;
  }
  return Math.round((clampNumber(value, 0, max) / max) * 100);
};

const getCameraStatus = (params: {
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
}) => {
  const { spotConfig, spotImageUrl, spotImageLoading, spotImageError, spotLastSuccessAt } = params;
  if (!spotConfig) {
    return null;
  }
  const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
  const now = Date.now();
  const delayMs = spotLastSuccessAt ? now - spotLastSuccessAt : null;

  if (spotImageError) {
    return { type: 'error', title: spotImageError, detail: '' };
  }
  if (!spotImageUrl || spotImageLoading || spotLastSuccessAt === null) {
    return { type: 'loading', title: '카메라 연결 중', detail: '' };
  }
  if (delayMs !== null && delayMs > refreshMs * 5) {
    return { type: 'danger', title: '이미지 수신 지연', detail: `지연 ${Math.round(delayMs / 1000)}초` };
  }
  if (delayMs !== null && delayMs > refreshMs * 2) {
    return { type: 'warn', title: '이미지 지연 감지', detail: `지연 ${Math.round(delayMs / 1000)}초` };
  }
  return null;
};

function App() {
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [centralStatus, setCentralStatus] = useState<CentralStatus | null>(null);
  const [centralSyncBusy, setCentralSyncBusy] = useState(false);
  const [reconnectBusy, setReconnectBusy] = useState(false);
  const [diagnosisBusy, setDiagnosisBusy] = useState(false);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsInfo, setSettingsInfo] = useState<string | null>(null);
  const [settingsForm, setSettingsForm] = useState<SettingsFormState | null>(null);
  const [settingsBaseline, setSettingsBaseline] = useState<SettingsFormState | null>(null);
  const [settingsConfigPath, setSettingsConfigPath] = useState<string | null>(null);
  const [configWritable, setConfigWritable] = useState<boolean | null>(null);
  const [thresholdConfig, setThresholdConfig] = useState<ThresholdState>(() => buildThresholdStateFromConfig());
  const [settingsRestartRequired, setSettingsRestartRequired] = useState(false);
  const [settingsApplyResult, setSettingsApplyResult] = useState<ConfigApplyResult | null>(null);
  const [externalConfigPending, setExternalConfigPending] = useState<ConfigSnapshot | null>(null);
  const [externalConfigPendingAt, setExternalConfigPendingAt] = useState<number | null>(null);
  const [settingsToast, setSettingsToast] = useState<{ message: string; level: 'ok' | 'warn' | 'error' } | null>(null);
  const [overrideEnabled, setOverrideEnabled] = useState(false);
  const [overrideMeta, setOverrideMeta] = useState<ConfigSnapshot["meta"] | null>(null);
  const [overrideBusy, setOverrideBusy] = useState(false);
  const [connectionTests, setConnectionTests] = useState<ConnectionTestState>({});
  const [connectionTestBusy, setConnectionTestBusy] = useState<Record<ConnectionTargetKey, boolean>>({
    extruder: false,
    ls_plc: false,
    spot: false,
  });
  const [pathHealth, setPathHealth] = useState<PathHealthState>({});
  const [pathCheckBusy, setPathCheckBusy] = useState(false);
  const [commLogPath, setCommLogPath] = useState<string | null>(null);
  const [commLogInfoError, setCommLogInfoError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [spotConfig, setSpotConfig] = useState<SpotConfig | null>(null);
  const [spotImageUrl, setSpotImageUrl] = useState('');
  const [spotImageError, setSpotImageError] = useState<string | null>(null);
  const [spotImageLoading, setSpotImageLoading] = useState(false);
  const [spotLastSuccessAt, setSpotLastSuccessAt] = useState<number | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);
  const [layoutEditing, setLayoutEditing] = useState(false);
  const [layoutSaveMessage, setLayoutSaveMessage] = useState<string | null>(null);
  const [layoutSaveError, setLayoutSaveError] = useState<string | null>(null);
  const [layoutRestoreMessage, setLayoutRestoreMessage] = useState<string | null>(null);
  const [layoutRestoreError, setLayoutRestoreError] = useState<string | null>(null);
  const [layoutSnapshot, setLayoutSnapshot] = useState<LayoutSnapshot | null>(null);
  const [, setLayoutLoadError] = useState<string | null>(null);
  const [layoutSlots, setLayoutSlots] = useState<LayoutSlotSummary[]>([]);
  const [layoutActiveId, setLayoutActiveId] = useState<string | null>(null);

  const spotHasImage = useRef(false);
  const saveMessageTimerRef = useRef<number | null>(null);
  const restoreMessageTimerRef = useRef<number | null>(null);
  const settingsToastTimerRef = useRef<number | null>(null);
  const settingsFingerprintRef = useRef<string | null>(null);
  const settingsExternalNotifyRef = useRef<string | null>(null);
  const statusRef = useRef<string | null>(null);
  const spotAlertRef = useRef(false);
  const cameraStatusRef = useRef<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const settingsScrollRef = useRef<HTMLDivElement | null>(null);
  const settingsSectionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastSpotValue = useLastValidNumber(data?.Spot);
  const spotAlertFallback = useSustainedFlag(
    lastSpotValue !== null && lastSpotValue >= SPOT_WARN_TEMP,
    ALERT_HOLD_MS
  );
  const spotAlertActive = data?.Computed?.spot_warning ?? spotAlertFallback;
  const thresholdState = useMemo(() => {
    if (settingsOpen && settingsForm) {
      return buildThresholdStateFromForm(settingsForm);
    }
    return thresholdConfig;
  }, [settingsOpen, settingsForm, thresholdConfig]);
  const settingsSections = useMemo(
    () => [
      { id: 'settings-summary', label: '요약' },
      { id: 'settings-central', label: '중앙 설정' },
      { id: 'settings-comm', label: '통신 설정' },
      { id: 'settings-spot', label: 'SPOT 카메라' },
      { id: 'settings-storage', label: '저장 설정' },
      { id: 'settings-logging', label: '로그 회전' },
      { id: 'settings-alerts', label: '알림/임계값' },
      { id: 'settings-security', label: '보안' },
    ],
    []
  );
  const connectionTestTargets = useMemo(
    () => [
      { key: 'extruder' as const, label: 'Extruder' },
      { key: 'ls_plc' as const, label: 'LS PLC' },
      { key: 'spot' as const, label: 'SPOT Camera' },
    ],
    []
  );
  const thresholdItems = useMemo<ThresholdItem[]>(
    () => [
      {
        key: 'speed',
        label: '속도',
        unit: 'mm/s',
        enableField: 'thresholdSpeedEnabled',
        valueField: 'thresholdSpeedValue',
      },
      {
        key: 'press',
        label: '압력',
        unit: 'bar',
        enableField: 'thresholdPressEnabled',
        valueField: 'thresholdPressValue',
      },
      {
        key: 'spot',
        label: 'SPOT',
        unit: '℃',
        enableField: 'thresholdSpotEnabled',
        valueField: 'thresholdSpotValue',
      },
      {
        key: 'temp_f',
        label: '컨테이너 앞',
        unit: '℃',
        enableField: 'thresholdTempFEnabled',
        valueField: 'thresholdTempFValue',
      },
      {
        key: 'temp_b',
        label: '컨테이너 뒤',
        unit: '℃',
        enableField: 'thresholdTempBEnabled',
        valueField: 'thresholdTempBValue',
      },
      {
        key: 'billet',
        label: '빌렛 길이',
        unit: 'mm',
        enableField: 'thresholdBilletEnabled',
        valueField: 'thresholdBilletValue',
      },
      {
        key: 'billet_temp',
        label: '빌렛 온도',
        unit: '℃',
        enableField: 'thresholdBilletTempEnabled',
        valueField: 'thresholdBilletTempValue',
      },
      {
        key: 'at_temp',
        label: '환경 온도',
        unit: '℃',
        enableField: 'thresholdAtTempEnabled',
        valueField: 'thresholdAtTempValue',
      },
      {
        key: 'at_pre',
        label: '환경 습도',
        unit: '%',
        enableField: 'thresholdAtPreEnabled',
        valueField: 'thresholdAtPreValue',
      },
      {
        key: 'count',
        label: '카운트',
        unit: 'ea',
        enableField: 'thresholdCountEnabled',
        valueField: 'thresholdCountValue',
      },
      {
        key: 'endpos',
        label: '종료 위치',
        unit: 'mm',
        enableField: 'thresholdEndPosEnabled',
        valueField: 'thresholdEndPosValue',
      },
    ],
    []
  );
  const [activeSettingsSection, setActiveSettingsSection] = useState(settingsSections[0]?.id ?? '');


  // --- Data Fetching Hooks (Same as before) ---


  useEffect(() => {
    return () => {
      if (saveMessageTimerRef.current !== null) {
        window.clearTimeout(saveMessageTimerRef.current);
      }
      if (restoreMessageTimerRef.current !== null) {
        window.clearTimeout(restoreMessageTimerRef.current);
      }
      if (settingsToastTimerRef.current !== null) {
        window.clearTimeout(settingsToastTimerRef.current);
      }
    };
  }, []);

  const fetchLayoutSlots = useCallback(async () => {
    try {
      const res = await axios.get<LayoutSlotsResponse>(`${API_BASE}/api/layouts`);
      setLayoutSlots(res.data?.slots ?? []);
      setLayoutActiveId(res.data?.active_id ?? null);
    } catch (error) {
      console.error('Layout slots load failed', error);
      setLayoutSlots([]);
      setLayoutActiveId(null);
    }
  }, []);

  const readLegacyLayoutSnapshot = useCallback((): LayoutSnapshot | null => {
    try {
      const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      let layout: LayoutMap = {};
      if (Array.isArray(parsed)) {
        layout = buildLayoutMapFromArray(parsed);
      } else if (parsed && typeof parsed === 'object') {
        layout = buildLayoutMapFromObject(parsed as Record<string, unknown>);
      }
      if (Object.keys(layout).length === 0) {
        return null;
      }
      const cols = localStorage.getItem(LAYOUT_COLS_KEY);
      return {
        layout,
        cols,
        version: 'v1',
      };
    } catch (error) {
      console.error('Legacy layout parse failed', error);
      return null;
    }
  }, []);

  const migrateLegacyLayout = useCallback(async () => {
    const legacy = readLegacyLayoutSnapshot();
    if (!legacy) {
      return null;
    }
    const normalized = normalizeLayoutMap(legacy.layout, legacy.cols ?? null);
    const payload = {
      name: '이전 레이아웃',
      layout: normalized.layout,
      cols: normalized.cols ?? CURRENT_LAYOUT_COLS,
      version: 'v2',
    };
    try {
      const res = await axios.post(`${API_BASE}/api/layouts`, payload);
      localStorage.removeItem(LAYOUT_STORAGE_KEY);
      localStorage.removeItem(LAYOUT_COLS_KEY);
      localStorage.removeItem(LAYOUT_BACKUP_KEY);
      return {
        layout: payload.layout,
        cols: payload.cols,
        version: payload.version,
        updated_at: res.data?.updated_at ?? null,
      } as LayoutSnapshot;
    } catch (error) {
      console.error('Legacy layout migration failed', error);
      return {
        layout: payload.layout,
        cols: payload.cols,
        version: payload.version,
      } as LayoutSnapshot;
    }
  }, [readLegacyLayoutSnapshot]);

  const loadLayoutSnapshot = useCallback(async () => {
    setLayoutLoadError(null);
    try {
      const res = await axios.get<LayoutSnapshot>(`${API_BASE}/api/layout`);
      const snapshot = res.data;
      if (snapshot && snapshot.layout) {
        const normalized = normalizeLayoutMap(snapshot.layout, snapshot.cols ?? null);
        setLayoutSnapshot({
          ...snapshot,
          layout: normalized.layout,
          cols: normalized.cols,
        });
      } else {
        setLayoutSnapshot(null);
      }
    } catch (error) {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined;
      if (status === 404) {
        const migrated = await migrateLegacyLayout();
        setLayoutSnapshot(migrated);
      } else {
        console.error('Layout load failed', error);
        setLayoutLoadError('레이아웃 로드 실패');
      }
    } finally {
      await fetchLayoutSlots();
    }
  }, [fetchLayoutSlots, migrateLegacyLayout]);

  useEffect(() => {
    loadLayoutSnapshot();
  }, [loadLayoutSnapshot]);

  useEffect(() => {
    if (!layoutEditing) {
      return;
    }
    fetchLayoutSlots();
  }, [layoutEditing, fetchLayoutSlots]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    fetchLayoutSlots();
  }, [menuOpen, fetchLayoutSlots]);

  useEffect(() => {
    const fetchData = async () => {
      const start = performance.now();
      try {
        const res = await axios.get<FactoryData>(`${API_BASE}/api/data`);
        setData(res.data);
        setConnected(true);
        setLastDataAt(Date.now());
        setLatencyMs(Math.round(performance.now() - start));
      } catch (err) {
        console.error('API Error', err);
        setConnected(false);
        setLatencyMs(null);
      }
    };
    const interval = setInterval(fetchData, 500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const tick = window.setInterval(() => setNowTick(Date.now()), 500);
    return () => window.clearInterval(tick);
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await axios.get<HealthSnapshot>(`${API_BASE}/health`);
      setHealth(res.data);
      return res.data;
    } catch (error) {
      setHealth(null);
      throw error;
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get<StatsSnapshot>(`${API_BASE}/stats`);
      setStats(res.data);
      return res.data;
    } catch (error) {
      setStats(null);
      throw error;
    }
  };

  const fetchCentralStatus = async () => {
    try {
      const res = await axios.get<CentralStatus>(`${API_BASE}/api/config/central-status`);
      setCentralStatus(res.data);
      return res.data;
    } catch (error) {
      setCentralStatus(null);
      throw error;
    }
  };

  const handleCentralSync = async () => {
    if (centralSyncBusy) {
      return;
    }
    setCentralSyncBusy(true);
    setSettingsError(null);
    setSettingsInfo(null);
    try {
      const res = await axios.post<CentralSyncResult>(`${API_BASE}/api/config/sync`);
      const status = res.data?.status ?? 'UNKNOWN';
      const message =
        status === 'APPLIED'
          ? '중앙 설정이 적용되었습니다.'
          : status === 'NO_CHANGE'
            ? '중앙 설정 변경 없음.'
            : status === 'SKIPPED'
              ? '로컬 오버라이드로 인해 적용이 보류되었습니다.'
              : status === 'DISABLED'
                ? '중앙 설정이 설정되지 않았습니다.'
                : '중앙 설정 동기화 실패.';
      setSettingsInfo(message);
      await fetchCentralStatus();
      if (settingsOpen) {
        await loadSettings();
      }
    } catch (error) {
      console.error('Central sync failed', error);
      setSettingsError('중앙 설정 동기화에 실패했습니다.');
    } finally {
      setCentralSyncBusy(false);
    }
  };

  const handleReconnect = async () => {
    if (reconnectBusy) return;
    setReconnectBusy(true);
    try {
      await axios.post(`${API_BASE}/api/control/reconnect`);
      await fetchHealth();
      window.alert('Reconnect requested. Check status badge.');
    } catch (error) {
      console.error('Reconnect failed', error);
      window.alert('Reconnect failed.');
    } finally {
      setReconnectBusy(false);
    }
  };

  const handleDiagnosis = async () => {
    if (diagnosisBusy) return;
    setDiagnosisBusy(true);
    try {
      const snapshot = await fetchHealth();
      const lastUpdate = snapshot.last_update
        ? new Date(snapshot.last_update * 1000).toLocaleString()
        : 'n/a';
      const detail = [
        `Mode: ${snapshot.mode}`,
        `Driver: ${snapshot.driver_connected ? 'OK' : 'Down'}`,
        `Thread: ${snapshot.thread_alive ? 'Alive' : 'Stopped'}`,
        `Last Update: ${lastUpdate}`,
      ].join('\n');
      window.alert(detail);
    } catch (error) {
      console.error('Diagnosis failed', error);
      window.alert('Diagnosis failed.');
    } finally {
      setDiagnosisBusy(false);
    }
  };

  const pushNotification = useCallback(
    (title: string, message: string, level: NotificationLevel) => {
      const item: NotificationItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        time: Date.now(),
        title,
        message,
        level,
      };
      setNotifications((prev) => [item, ...prev].slice(0, MAX_NOTIFICATIONS));
      if (!notificationsOpen) {
        setUnreadCount((prev) => Math.min(prev + 1, MAX_NOTIFICATIONS));
      }
    },
    [notificationsOpen]
  );

  const clearNotifications = () => {
    setNotifications([]);
    setUnreadCount(0);
  };

  useEffect(() => {
    if (notificationsOpen) {
      setUnreadCount(0);
    }
  }, [notificationsOpen]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const handleClick = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (!menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    window.addEventListener('mousedown', handleClick);
    return () => window.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  const buildSettingsFingerprint = useCallback((snapshot: ConfigSnapshot) => {
    return JSON.stringify({
      config_path: snapshot.config_path ?? '',
      encoding: snapshot.encoding ?? '',
      restart_required: Boolean(snapshot.restart_required),
      values: snapshot.values ?? {},
      meta: snapshot.meta ?? {},
    });
  }, []);

  const buildSettingsFormFromSnapshot = useCallback((snapshot: ConfigSnapshot) => {
    const values = snapshot.values;
    const thresholds = values.thresholds ?? {};
    const thresholdsValues = thresholds.values ?? {};
    const thresholdsEnable = thresholds.enable ?? {};
    const toStr = (value?: string) => value ?? '';
    const toBool = (value?: boolean) => Boolean(value);
    const nextThresholdState = buildThresholdStateFromConfig(thresholds);
    const nextForm: SettingsFormState = {
      extruderIp: values.extruder.ip ?? '',
      extruderPort: values.extruder.port?.toString() ?? '',
      lsIp: values.ls_plc.ip ?? '',
      lsPort: values.ls_plc.port?.toString() ?? '',
      spotIp: values.spot.ip ?? '',
      spotRefreshInterval: values.spot.refresh_interval?.toString() ?? '',
      thresholdMasterOn: toBool(thresholdsEnable.master_on),
      thresholdSpeedEnabled: toBool(thresholdsEnable.speed),
      thresholdSpeedValue: toStr(thresholdsValues.speed),
      thresholdPressEnabled: toBool(thresholdsEnable.press),
      thresholdPressValue: toStr(thresholdsValues.press),
      thresholdSpotEnabled: toBool(thresholdsEnable.spot),
      thresholdSpotValue: toStr(thresholdsValues.spot),
      thresholdTempFEnabled: toBool(thresholdsEnable.temp_f),
      thresholdTempFValue: toStr(thresholdsValues.temp_f),
      thresholdTempBEnabled: toBool(thresholdsEnable.temp_b),
      thresholdTempBValue: toStr(thresholdsValues.temp_b),
      thresholdBilletEnabled: toBool(thresholdsEnable.billet),
      thresholdBilletValue: toStr(thresholdsValues.billet),
      thresholdBilletTempEnabled: toBool(thresholdsEnable.billet_temp),
      thresholdBilletTempValue: toStr(thresholdsValues.billet_temp),
      thresholdAtTempEnabled: toBool(thresholdsEnable.at_temp),
      thresholdAtTempValue: toStr(thresholdsValues.at_temp),
      thresholdAtPreEnabled: toBool(thresholdsEnable.at_pre),
      thresholdAtPreValue: toStr(thresholdsValues.at_pre),
      thresholdCountEnabled: toBool(thresholdsEnable.count),
      thresholdCountValue: toStr(thresholdsValues.count),
      thresholdEndPosEnabled: toBool(thresholdsEnable.endpos),
      thresholdEndPosValue: toStr(thresholdsValues.endpos),
      logPath: values.settings.logpath ?? '',
      snapshotPath: values.settings.snapshotpath ?? '',
      autoSave: Boolean(values.settings.autosave),
      rotationEnabled: values.logging.rotation_enabled ?? true,
      rotationMode: values.logging.rotation_mode ?? 'BILLET',
      cycleIdleTime: values.logging.cycle_idle_time?.toString() ?? '',
      cycleThresholdPress: values.logging.cycle_threshold_press?.toString() ?? '',
      password: '',
      passwordSet: Boolean(values.settings.password_set),
    };
    return { form: nextForm, thresholds: nextThresholdState };
  }, []);

  const applySettingsSnapshot = useCallback(
    (snapshot: ConfigSnapshot) => {
      const { form, thresholds } = buildSettingsFormFromSnapshot(snapshot);
      setSettingsForm(form);
      setSettingsBaseline(form);
      setThresholdConfig(thresholds);
      setSettingsConfigPath(snapshot.config_path ?? null);
      setConfigWritable(snapshot.config_writable ?? null);
      setSettingsRestartRequired(Boolean(snapshot.restart_required));
      setSettingsApplyResult(snapshot.apply ?? null);
      setOverrideEnabled(Boolean(snapshot.meta?.override_enabled));
      setOverrideMeta(snapshot.meta ?? null);
    },
    [buildSettingsFormFromSnapshot]
  );

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    setSettingsConfigPath(null);
    setConfigWritable(null);
    setSettingsBaseline(null);
    setSettingsRestartRequired(false);
    setPathHealth({});
    try {
      const res = await axios.get<ConfigSnapshot>(`${API_BASE}/api/config`);
      applySettingsSnapshot(res.data);
      const fingerprint = buildSettingsFingerprint(res.data);
      settingsFingerprintRef.current = fingerprint;
      settingsExternalNotifyRef.current = null;
      setExternalConfigPending(null);
      setExternalConfigPendingAt(null);
    } catch (error) {
      console.error('Config load failed', error);
      setSettingsError('설정을 불러오지 못했습니다.');
    } finally {
      setSettingsLoading(false);
    }
  }, [applySettingsSnapshot, buildSettingsFingerprint]);

  const loadThresholdConfig = useCallback(async () => {
    try {
      const res = await axios.get<ConfigSnapshot>(`${API_BASE}/api/config`);
      setThresholdConfig(buildThresholdStateFromConfig(res.data.values?.thresholds));
    } catch (error) {
      console.error('Threshold config load failed', error);
    }
  }, []);

  useEffect(() => {
    loadThresholdConfig();
  }, [loadThresholdConfig]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }
    setSettingsInfo(null);
    loadSettings();
    fetchCentralStatus().catch(() => null);
    (async () => {
      try {
        const res = await axios.get<CommLogInfo>(`${API_BASE}/api/logs/comm-metrics`);
        setCommLogPath(res.data?.path ?? null);
        setCommLogInfoError(null);
      } catch (error) {
        setCommLogInfoError('통신 로그 경로를 불러오지 못했습니다.');
      }
    })();
  }, [settingsOpen, loadSettings]);

  useEffect(() => {
    if (!settingsOpen) {
      settingsFingerprintRef.current = null;
      settingsExternalNotifyRef.current = null;
      setExternalConfigPending(null);
      setExternalConfigPendingAt(null);
      setCommLogPath(null);
      setCommLogInfoError(null);
    }
  }, [settingsOpen]);

  const logPathValue = settingsForm?.logPath ?? '';
  const snapshotPathValue = settingsForm?.snapshotPath ?? '';
  const settingsReady = settingsForm !== null;
  const configReadOnly = configWritable === false;

  const validationErrors = useMemo(() => {
    if (!settingsForm) {
      return {} as Partial<Record<keyof SettingsFormState, string>>;
    }
    const errors: Partial<Record<keyof SettingsFormState, string>> = {};
    if (!isValidIp(settingsForm.extruderIp)) {
      errors.extruderIp = 'IPv4 형식이 아닙니다.';
    }
    if (!isValidPort(settingsForm.extruderPort)) {
      errors.extruderPort = '1-65535 범위를 입력하세요.';
    }
    if (!isValidIp(settingsForm.lsIp)) {
      errors.lsIp = 'IPv4 형식이 아닙니다.';
    }
    if (!isValidPort(settingsForm.lsPort)) {
      errors.lsPort = '1-65535 범위를 입력하세요.';
    }
    if (!isValidIp(settingsForm.spotIp)) {
      errors.spotIp = 'IPv4 형식이 아닙니다.';
    }
    const thresholdValueFields: Array<keyof SettingsFormState> = [
      'thresholdSpeedValue',
      'thresholdPressValue',
      'thresholdSpotValue',
      'thresholdTempFValue',
      'thresholdTempBValue',
      'thresholdBilletValue',
      'thresholdBilletTempValue',
      'thresholdAtTempValue',
      'thresholdAtPreValue',
      'thresholdCountValue',
      'thresholdEndPosValue',
    ];
    thresholdValueFields.forEach((field) => {
      const value = settingsForm[field] as string;
      if (!isValidNumberInput(value)) {
        errors[field] = '숫자만 입력하세요.';
      }
    });
    return errors;
  }, [settingsForm]);
  const hasValidationError = Object.keys(validationErrors).length > 0;



  const hasPathError = ['log', 'snapshot'].some(
    (key) => pathHealth[key as 'log' | 'snapshot']?.status === 'ERROR'
  );
  const hasPathWarn = ['log', 'snapshot'].some(
    (key) => pathHealth[key as 'log' | 'snapshot']?.status === 'WARN'
  );
  const logPathStatus = pathHealth.log?.status ?? 'UNKNOWN';
  const snapshotPathStatus = pathHealth.snapshot?.status ?? 'UNKNOWN';
  const logPathFieldState = logPathStatus === 'ERROR' ? 'error' : logPathStatus === 'WARN' ? 'warn' : '';
  const snapshotPathFieldState =
    snapshotPathStatus === 'ERROR' ? 'error' : snapshotPathStatus === 'WARN' ? 'warn' : '';
  const applyApplied = settingsApplyResult?.applied ?? [];
  const applyPending = settingsApplyResult?.pending ?? [];
  const formatApplyKey = useCallback((key: string) => APPLY_KEY_LABELS[key] ?? key, []);
  const applyDetails = useMemo(
    () => ({
      applied: applyApplied.map(formatApplyKey),
      pending: applyPending.map(formatApplyKey),
    }),
    [applyApplied, applyPending, formatApplyKey]
  );


  const settingsDirtyCount = useMemo(() => {
    if (!settingsForm || !settingsBaseline) {
      return 0;
    }
    const keys: Array<keyof SettingsFormState> = [
      'extruderIp',
      'extruderPort',
      'lsIp',
      'lsPort',
      'spotIp',
      'spotRefreshInterval',
      'thresholdMasterOn',
      'thresholdSpeedEnabled',
      'thresholdSpeedValue',
      'thresholdPressEnabled',
      'thresholdPressValue',
      'thresholdSpotEnabled',
      'thresholdSpotValue',
      'thresholdTempFEnabled',
      'thresholdTempFValue',
      'thresholdTempBEnabled',
      'thresholdTempBValue',
      'thresholdBilletEnabled',
      'thresholdBilletValue',
      'thresholdBilletTempEnabled',
      'thresholdBilletTempValue',
      'thresholdAtTempEnabled',
      'thresholdAtTempValue',
      'thresholdAtPreEnabled',
      'thresholdAtPreValue',
      'thresholdCountEnabled',
      'thresholdCountValue',
      'thresholdEndPosEnabled',
      'thresholdEndPosValue',
      'logPath',
      'snapshotPath',
      'autoSave',
      'rotationEnabled',
      'rotationMode',
      'cycleIdleTime',
      'cycleThresholdPress',
      'password',
    ];

    return keys.reduce((count, key) => {
      if (key === 'password') {
        return settingsForm.password.trim() ? count + 1 : count;
      }
      const current = settingsForm[key];
      const baseline = settingsBaseline[key];
      if (typeof current === 'boolean' || typeof baseline === 'boolean') {
        return current !== baseline ? count + 1 : count;
      }
      return String(current ?? '').trim() !== String(baseline ?? '').trim() ? count + 1 : count;
    }, 0);
  }, [settingsForm, settingsBaseline]);
  const hasSettingsChanges = settingsDirtyCount > 0;
  const updateSettingsField = (field: keyof SettingsFormState, value: string | boolean) => {
    setSettingsForm((prev) => {
      if (!prev) return prev;
      return { ...prev, [field]: value };
    });
  };

  useEffect(() => {
    const poll = async () => {
      await fetchHealth().catch(() => null);
      await fetchStats().catch(() => null);
    };
    poll();
    const interval = window.setInterval(poll, 5000);
    return () => window.clearInterval(interval);
  }, []);

  const showSettingsToast = useCallback((message: string, level: 'ok' | 'warn' | 'error') => {
    setSettingsToast({ message, level });
    if (settingsToastTimerRef.current !== null) {
      window.clearTimeout(settingsToastTimerRef.current);
    }
    settingsToastTimerRef.current = window.setTimeout(() => {
      setSettingsToast(null);
      settingsToastTimerRef.current = null;
    }, 2500);
  }, []);

  const handleExternalRefresh = useCallback(() => {
    if (!externalConfigPending) {
      return;
    }
    if (hasSettingsChanges) {
      const ok = window.confirm('외부 변경 내용을 불러오면 현재 입력 중인 값이 사라집니다. 계속할까요?');
      if (!ok) {
        return;
      }
    }
    applySettingsSnapshot(externalConfigPending);
    const fingerprint = buildSettingsFingerprint(externalConfigPending);
    settingsFingerprintRef.current = fingerprint;
    settingsExternalNotifyRef.current = null;
    setExternalConfigPending(null);
    setExternalConfigPendingAt(null);
    setSettingsError(null);
    setSettingsInfo('외부 변경 내용을 반영했습니다.');
    showSettingsToast('외부 변경을 반영했습니다.', 'ok');
  }, [
    externalConfigPending,
    hasSettingsChanges,
    applySettingsSnapshot,
    buildSettingsFingerprint,
    showSettingsToast,
  ]);

  const handleExternalIgnore = useCallback(() => {
    if (!externalConfigPending) {
      return;
    }
    const fingerprint = buildSettingsFingerprint(externalConfigPending);
    settingsExternalNotifyRef.current = fingerprint;
    setExternalConfigPending(null);
    setExternalConfigPendingAt(null);
    showSettingsToast('외부 변경 알림을 보류했습니다.', 'warn');
  }, [externalConfigPending, buildSettingsFingerprint, showSettingsToast]);

  const handleCopyCommLogPath = useCallback(async () => {
    if (!commLogPath) {
      return;
    }
    try {
      await navigator.clipboard.writeText(commLogPath);
      showSettingsToast('통신 로그 경로를 복사했습니다.', 'ok');
    } catch (error) {
      console.error('Clipboard copy failed', error);
      showSettingsToast('복사에 실패했습니다.', 'error');
    }
  }, [commLogPath, showSettingsToast]);

  const handleOpenCommLogPath = useCallback(async () => {
    if (!commLogPath) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/logs/comm-metrics/open`);
      showSettingsToast('통신 로그 폴더를 열었습니다.', 'ok');
    } catch (error) {
      console.error('Open comm log path failed', error);
      showSettingsToast('폴더 열기에 실패했습니다.', 'error');
    }
  }, [commLogPath, showSettingsToast]);

  const handleOpenCommLogFile = useCallback(async () => {
    if (!commLogPath) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/logs/comm-metrics/open-file`);
      showSettingsToast('통신 로그 파일을 열었습니다.', 'ok');
    } catch (error) {
      console.error('Open comm log file failed', error);
      showSettingsToast('파일 열기에 실패했습니다.', 'error');
    }
  }, [commLogPath, showSettingsToast]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }
    const poll = async () => {
      if (settingsLoading) {
        return;
      }
      try {
        const res = await axios.get<ConfigSnapshot>(`${API_BASE}/api/config`);
        const fingerprint = buildSettingsFingerprint(res.data);
        if (!settingsFingerprintRef.current) {
          settingsFingerprintRef.current = fingerprint;
          return;
        }
        if (fingerprint === settingsFingerprintRef.current) {
          return;
        }
        if (hasSettingsChanges) {
          if (settingsExternalNotifyRef.current !== fingerprint) {
            showSettingsToast('설정 파일이 외부에서 변경되었습니다. 편집 중이어서 자동 갱신을 보류합니다.', 'warn');
            settingsExternalNotifyRef.current = fingerprint;
            setExternalConfigPending(res.data);
            setExternalConfigPendingAt(Date.now());
          }
          return;
        }
        applySettingsSnapshot(res.data);
        settingsFingerprintRef.current = fingerprint;
        settingsExternalNotifyRef.current = null;
        setExternalConfigPending(null);
        setExternalConfigPendingAt(null);
        showSettingsToast('설정 파일 변경을 감지하여 화면을 갱신했습니다.', 'ok');
      } catch (error) {
        console.error('Settings auto-refresh failed', error);
      }
    };
    poll();
    const interval = window.setInterval(poll, SETTINGS_AUTO_REFRESH_MS);
    return () => window.clearInterval(interval);
  }, [
    settingsOpen,
    settingsLoading,
    hasSettingsChanges,
    applySettingsSnapshot,
    buildSettingsFingerprint,
    showSettingsToast,
  ]);

  const handleSaveSettings = async () => {
    if (!settingsForm) {
      return;
    }
    if (configReadOnly) {
      setSettingsError('설정 파일이 읽기 전용입니다. 관리자 권한 또는 파일 속성을 확인하세요.');
      return;
    }
    if (hasValidationError) {
      setSettingsError('입력값 형식을 확인하세요.');
      return;
    }
    if (!overrideEnabled && hasSettingsChanges) {
      setSettingsError('로컬 오버라이드가 비활성화되어 저장할 수 없습니다.');
      return;
    }
    if (pathCheckBusy) {
      setSettingsError('경로 검증이 진행 중입니다.');
      return;
    }
    if (!pathHealth.log || !pathHealth.snapshot) {
      setSettingsError('경로 검증이 필요합니다. 검사 버튼을 눌러주세요.');
      runPathHealthCheck();
      return;
    }
    if (hasPathError) {
      setSettingsError('저장 경로에 오류가 있습니다. 경로를 수정하세요.');
      return;
    }
    if (!hasSettingsChanges) {
      setSettingsInfo('변경 사항이 없습니다.');
      return;
    }
    const summary = buildSettingsChangeSummary();
    if (hasPathWarn) {
      summary.unshift('경로 상태 경고가 포함되어 있습니다.');
    }
    if (summary.length > 0) {
      const maxItems = 8;
      const shown = summary.slice(0, maxItems);
      const rest = summary.length - shown.length;
      const lines = rest > 0 ? [...shown, `외 ${rest}건`] : shown;
      const confirmMessage = [
        '다음 변경 사항을 저장할까요?',
        '',
        ...lines,
        '',
        '저장 후 재시작이 필요할 수 있습니다.',
      ].join('\n');
      if (!window.confirm(confirmMessage)) {
        return;
      }
    }
    setSettingsLoading(true);
    setSettingsError(null);
    setSettingsInfo(null);

    const toInt = (value: string) => {
      const parsed = Number.parseInt(value, 10);
      return Number.isFinite(parsed) ? parsed : undefined;
    };
    const toFloat = (value: string) => {
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : undefined;
    };
    const toThresholdValue = (value: string) => value.trim();

    const payload = {
      extruder: {
        ip: settingsForm.extruderIp.trim() || undefined,
        port: toInt(settingsForm.extruderPort),
      },
      ls_plc: {
        ip: settingsForm.lsIp.trim() || undefined,
        port: toInt(settingsForm.lsPort),
      },
      spot: {
        ip: settingsForm.spotIp.trim() || undefined,
        refresh_interval: toFloat(settingsForm.spotRefreshInterval),
      },
      thresholds: {
        enable: {
          master_on: settingsForm.thresholdMasterOn,
          speed: settingsForm.thresholdSpeedEnabled,
          press: settingsForm.thresholdPressEnabled,
          spot: settingsForm.thresholdSpotEnabled,
          temp_f: settingsForm.thresholdTempFEnabled,
          temp_b: settingsForm.thresholdTempBEnabled,
          billet: settingsForm.thresholdBilletEnabled,
          billet_temp: settingsForm.thresholdBilletTempEnabled,
          at_temp: settingsForm.thresholdAtTempEnabled,
          at_pre: settingsForm.thresholdAtPreEnabled,
          count: settingsForm.thresholdCountEnabled,
          endpos: settingsForm.thresholdEndPosEnabled,
        },
        values: {
          speed: toThresholdValue(settingsForm.thresholdSpeedValue),
          press: toThresholdValue(settingsForm.thresholdPressValue),
          spot: toThresholdValue(settingsForm.thresholdSpotValue),
          temp_f: toThresholdValue(settingsForm.thresholdTempFValue),
          temp_b: toThresholdValue(settingsForm.thresholdTempBValue),
          billet: toThresholdValue(settingsForm.thresholdBilletValue),
          billet_temp: toThresholdValue(settingsForm.thresholdBilletTempValue),
          at_temp: toThresholdValue(settingsForm.thresholdAtTempValue),
          at_pre: toThresholdValue(settingsForm.thresholdAtPreValue),
          count: toThresholdValue(settingsForm.thresholdCountValue),
          endpos: toThresholdValue(settingsForm.thresholdEndPosValue),
        },
      },
      settings: {
        logpath: settingsForm.logPath.trim() || undefined,
        snapshotpath: settingsForm.snapshotPath.trim() || undefined,
        autosave: settingsForm.autoSave,
        password: settingsForm.password.trim() || undefined,
      },
      logging: {
        rotation_enabled: settingsForm.rotationEnabled,
        rotation_mode: settingsForm.rotationMode,
        cycle_idle_time: toFloat(settingsForm.cycleIdleTime),
        cycle_threshold_press: toFloat(settingsForm.cycleThresholdPress),
      },
    };

    try {
      const res = await axios.post<ConfigUpdateResponse>(`${API_BASE}/api/config`, payload);
      const applyInfo = res.data?.apply ?? null;
      const pendingCount = applyInfo?.pending?.length ?? 0;
      const appliedCount = applyInfo?.applied?.length ?? 0;
      if (pendingCount > 0) {
        setSettingsInfo('일부 설정은 재시작 후 적용됩니다.');
      } else if (appliedCount > 0) {
        setSettingsInfo('설정이 저장되었습니다. 재시작 없이 적용되었습니다.');
      } else {
        setSettingsInfo('설정이 저장되었습니다.');
      }
      setSettingsRestartRequired(Boolean(res.data?.restart_required));
      setSettingsApplyResult(applyInfo);
      setSettingsBaseline({
        ...settingsForm,
        password: '',
        passwordSet: settingsForm.passwordSet || settingsForm.password.trim().length > 0,
      });
      setThresholdConfig(buildThresholdStateFromForm(settingsForm));
      updateSettingsField('password', '');
      const notificationMessage =
        pendingCount > 0
          ? `설정 저장 완료. 재시작 필요 항목 ${pendingCount}건.`
          : appliedCount > 0
            ? '설정 저장 완료. 즉시 적용됨.'
            : '설정 저장 완료.';
      pushNotification('설정 저장', notificationMessage, pendingCount > 0 ? 'warn' : 'info');
      showSettingsToast(notificationMessage, pendingCount > 0 ? 'warn' : 'ok');
      setExternalConfigPending(null);
      setExternalConfigPendingAt(null);
      settingsExternalNotifyRef.current = null;
    } catch (error) {
      console.error('Config save failed', error);
      setSettingsError('설정 저장에 실패했습니다.');
      pushNotification('설정 저장 실패', '설정 저장에 실패했습니다.', 'error');
      showSettingsToast('설정 저장 실패', 'error');
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleRestoreDefaults = async () => {
    if (settingsLoading) {
      return;
    }
    if (configReadOnly) {
      setSettingsError('설정 파일이 읽기 전용입니다. 관리자 권한 또는 파일 속성을 확인하세요.');
      return;
    }
    if (!overrideEnabled) {
      setSettingsError('로컬 오버라이드가 OFF 상태입니다.');
      return;
    }
    if (!window.confirm('기본값으로 복원하시겠습니까?')) {
      return;
    }
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      await axios.post(`${API_BASE}/api/config/restore-defaults`);
      setSettingsRestartRequired(true);
      setSettingsApplyResult(null);
      await loadSettings();
      showSettingsToast('기본값으로 복원했습니다.', 'ok');
    } catch (error) {
      console.error('Restore defaults failed', error);
      setSettingsError('기본값 복원에 실패했습니다.');
      showSettingsToast('기본값 복원 실패', 'error');
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleRestoreBackup = async () => {
    if (settingsLoading) {
      return;
    }
    if (configReadOnly) {
      setSettingsError('설정 파일이 읽기 전용입니다. 관리자 권한 또는 파일 속성을 확인하세요.');
      return;
    }
    if (!overrideEnabled) {
      setSettingsError('로컬 오버라이드가 OFF 상태입니다.');
      return;
    }
    if (!window.confirm('백업 파일(config.ini.bak)로 복원하시겠습니까?')) {
      return;
    }
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      await axios.post(`${API_BASE}/api/config/restore-backup`);
      setSettingsRestartRequired(true);
      setSettingsApplyResult(null);
      await loadSettings();
      showSettingsToast('백업으로 복원했습니다.', 'ok');
    } catch (error) {
      console.error('Restore backup failed', error);
      setSettingsError('백업 복원에 실패했습니다. 백업 파일을 확인하세요.');
      showSettingsToast('백업 복원 실패', 'error');
    } finally {
      setSettingsLoading(false);
    }
  };

  const runConnectionTest = async (target: ConnectionTargetKey) => {
    if (!settingsForm) {
      return;
    }
    if (target === 'extruder' && (validationErrors.extruderIp || validationErrors.extruderPort)) {
      setSettingsError('Extruder IP/Port 형식을 확인하세요.');
      return;
    }
    if (target === 'ls_plc' && (validationErrors.lsIp || validationErrors.lsPort)) {
      setSettingsError('LS PLC IP/Port 형식을 확인하세요.');
      return;
    }
    if (target === 'spot' && validationErrors.spotIp) {
      setSettingsError('SPOT IP 형식을 확인하세요.');
      return;
    }
    const toInt = (value: string) => {
      const parsed = Number.parseInt(value, 10);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const payload: Record<string, { ip?: string; port?: number | null; url?: string }> = {};
    if (target === 'extruder') {
      payload.extruder = {
        ip: settingsForm.extruderIp.trim() || undefined,
        port: toInt(settingsForm.extruderPort),
      };
    } else if (target === 'ls_plc') {
      payload.ls_plc = {
        ip: settingsForm.lsIp.trim() || undefined,
        port: toInt(settingsForm.lsPort),
      };
    } else if (target === 'spot') {
      const ip = settingsForm.spotIp.trim();
      payload.spot = {
        ip: ip || undefined,
        url: ip ? `http://${ip}/image.jpg` : undefined,
      };
    }

    setConnectionTestBusy((prev) => ({ ...prev, [target]: true }));
    try {
      const res = await axios.post<ConnectionTestResponse>(
        `${API_BASE}/api/control/test-connection`,
        payload
      );
      const results = res.data?.results ?? {};
      setConnectionTests((prev) => {
        const next = { ...prev };
        Object.entries(results).forEach(([key, value]) => {
          if (key === 'extruder' || key === 'ls_plc' || key === 'spot') {
            next[key] = {
              ok: Boolean(value.ok),
              latency_ms: value.latency_ms ?? null,
              message: value.message ?? '',
              tested_at: Date.now(),
            };
          }
        });
        return next;
      });
    } catch (error) {
      console.error('Connection test failed', error);
      setConnectionTests((prev) => ({
        ...prev,
        [target]: {
          ok: false,
          latency_ms: null,
          message: '연결 테스트 실패',
          tested_at: Date.now(),
        },
      }));
    } finally {
      setConnectionTestBusy((prev) => ({ ...prev, [target]: false }));
    }
  };


  const toggleOverride = async () => {
    if (overrideBusy || !settingsForm) {
      return;
    }
    const nextEnabled = !overrideEnabled;
    let password: string | undefined;
    if (settingsForm.passwordSet) {
      const input = window.prompt('로컬 오버라이드 변경을 위해 비밀번호를 입력하세요.');
      if (input === null) {
        return;
      }
      password = input;
    }
    setOverrideBusy(true);
    setSettingsError(null);
    try {
      const res = await axios.post(`${API_BASE}/api/config/override`, {
        enabled: nextEnabled,
        password,
        actor: 'local',
      });
      const meta = res.data?.meta ?? null;
      setOverrideEnabled(nextEnabled);
      setOverrideMeta(meta);
      setSettingsInfo(`로컬 오버라이드가 ${nextEnabled ? '활성화' : '비활성화'}되었습니다.`);
    } catch (error) {
      console.error('Override toggle failed', error);
      setSettingsError('로컬 오버라이드 변경에 실패했습니다.');
    } finally {
      setOverrideBusy(false);
    }
  };

  const runPathHealthCheck = useCallback(
    async (paths?: Array<{ key: 'log' | 'snapshot'; path: string }>) => {
      if (!settingsReady) {
        return;
      }
      const now = Date.now();
      const targets =
        paths ??
        [
          { key: 'log', path: logPathValue },
          { key: 'snapshot', path: snapshotPathValue },
        ];

      const payload: Array<{ key: string; path: string }> = [];
      const localResults: PathHealthState = {};

      targets.forEach((item) => {
        const trimmed = item.path.trim();
        if (!trimmed) {
          localResults[item.key] = {
            status: 'ERROR',
            exists: false,
            writable: false,
            is_dir: false,
            is_network: false,
            latency_ms: null,
            message: '경로 없음',
            checked_at: now,
          };
          return;
        }
        payload.push({ key: item.key, path: trimmed });
      });

      if (payload.length === 0) {
        setPathHealth((prev) => ({ ...prev, ...localResults }));
        return;
      }

      setPathCheckBusy(true);
      try {
        const res = await axios.post(`${API_BASE}/api/control/path-health`, { paths: payload });
        const results = res.data?.results ?? {};
        const merged: PathHealthState = { ...localResults };
        Object.entries(results).forEach(([key, value]) => {
          if (key === 'log' || key === 'snapshot') {
            merged[key] = {
              status: value.status ?? 'UNKNOWN',
              exists: Boolean(value.exists),
              writable: Boolean(value.writable),
              is_dir: Boolean(value.is_dir),
              is_network: Boolean(value.is_network),
              latency_ms: value.latency_ms ?? null,
              message: value.message ?? '',
              checked_at: now,
            };
          }
        });
        setPathHealth((prev) => ({ ...prev, ...merged }));
      } catch (error) {
        console.error('Path health check failed', error);
        setPathHealth((prev) => ({
          ...prev,
          log: prev.log ?? {
            status: 'UNKNOWN',
            exists: false,
            writable: false,
            is_dir: false,
            is_network: false,
            latency_ms: null,
            message: '검사 실패',
            checked_at: now,
          },
          snapshot: prev.snapshot ?? {
            status: 'UNKNOWN',
            exists: false,
            writable: false,
            is_dir: false,
            is_network: false,
            latency_ms: null,
            message: '검사 실패',
            checked_at: now,
          },
        }));
      } finally {
        setPathCheckBusy(false);
      }
    },
    [settingsReady, logPathValue, snapshotPathValue]
  );

  useEffect(() => {
    if (!settingsOpen || !settingsReady) {
      return;
    }
    const timer = window.setTimeout(() => {
      runPathHealthCheck();
    }, 500);
    return () => window.clearTimeout(timer);
  }, [settingsOpen, settingsReady, logPathValue, snapshotPathValue, runPathHealthCheck]);

  const createPath = useCallback(
    async (path: string) => {
      const trimmed = path.trim();
      if (!trimmed) {
        setSettingsError('경로가 비어 있습니다.');
        return;
      }
      try {
        await axios.post(`${API_BASE}/api/control/path-create`, { path: trimmed });
        await runPathHealthCheck();
      } catch (error) {
        console.error('Path create failed', error);
        setSettingsError('폴더 생성에 실패했습니다.');
      }
    },
    [runPathHealthCheck]
  );

  const getTestBadge = (result?: ConnectionTestResult) => {
    if (!result) {
      return { label: '미실행', className: 'idle' };
    }
    return result.ok
      ? { label: '성공', className: 'ok' }
      : { label: '실패', className: 'error' };
  };

  const formatTestTime = (result?: ConnectionTestResult) => {
    if (!result) {
      return '미실행';
    }
    return new Date(result.tested_at).toLocaleTimeString();
  };

  const getPathBadge = (result?: PathHealthResult) => {
    if (!result) {
      return { label: '미검사', className: 'idle' };
    }
    if (result.status === 'OK') {
      return { label: '정상', className: 'ok' };
    }
    if (result.status === 'WARN') {
      return { label: '경고', className: 'warn' };
    }
    if (result.status === 'ERROR') {
      return { label: '오류', className: 'error' };
    }
    return { label: '미확인', className: 'idle' };
  };

  const formatPathCheckTime = (result?: PathHealthResult) => {
    if (!result) {
      return '미검사';
    }
    return new Date(result.checked_at).toLocaleTimeString();
  };

  const formatPathMessage = (result?: PathHealthResult) => {
    if (!result) {
      return '경로 상태를 확인하세요.';
    }
    const map: Record<string, string> = {
      'Path not found (creatable)': '경로 없음(생성 가능)',
      'Not a directory': '디렉터리가 아님',
      'Write permission denied': '쓰기 권한 없음',
      'Invalid path format': '경로 형식이 올바르지 않습니다.',
      'Network drive unavailable': '네트워크 드라이브가 연결되어 있지 않습니다.',
      'Network path latency': '네트워크 경로 지연',
      OK: '정상',
    };
    return map[result.message] ?? result.message;
  };

  const getCentralBadge = (status?: string, configured?: boolean) => {
    if (configured === false) {
      return { label: '미설정', className: 'idle' };
    }
    if (configured === undefined) {
      return { label: '확인 중', className: 'idle' };
    }
    if (!status) {
      return { label: '미확인', className: 'idle' };
    }
    if (status === 'APPLIED') {
      return { label: '적용', className: 'ok' };
    }
    if (status === 'NO_CHANGE') {
      return { label: '변경 없음', className: 'ok' };
    }
    if (status === 'SKIPPED') {
      return { label: '보류', className: 'warn' };
    }
    if (status === 'FAILED') {
      return { label: '실패', className: 'error' };
    }
    if (status === 'DISABLED') {
      return { label: '미설정', className: 'idle' };
    }
    return { label: status, className: 'idle' };
  };

  const formatCentralTime = (result?: CentralSyncResult) => {
    if (!result?.at) {
      return '미실행';
    }
    return formatTime(result.at * 1000);
  };

  const isSettingsFieldDirty = useCallback(
    (field: keyof SettingsFormState) => {
      if (!settingsForm || !settingsBaseline) {
        return false;
      }
      if (field === 'password') {
        return settingsForm.password.trim().length > 0;
      }
      const current = settingsForm[field];
      const baseline = settingsBaseline[field];
      if (typeof current === 'boolean' || typeof baseline === 'boolean') {
        return current !== baseline;
      }
      return String(current ?? '').trim() !== String(baseline ?? '').trim();
    },
    [settingsForm, settingsBaseline]
  );
  const settingsSectionFieldMap = useMemo(
    () => ({
      'settings-summary': [],
      'settings-central': [],
      'settings-comm': [
        'extruderIp',
        'extruderPort',
        'lsIp',
        'lsPort',
      ],
      'settings-spot': ['spotIp', 'spotRefreshInterval'],
      'settings-storage': ['logPath', 'snapshotPath', 'autoSave'],
      'settings-logging': ['rotationEnabled', 'rotationMode', 'cycleIdleTime', 'cycleThresholdPress'],
      'settings-alerts': [
        'thresholdMasterOn',
        'thresholdSpeedEnabled',
        'thresholdSpeedValue',
        'thresholdPressEnabled',
        'thresholdPressValue',
        'thresholdSpotEnabled',
        'thresholdSpotValue',
        'thresholdTempFEnabled',
        'thresholdTempFValue',
        'thresholdTempBEnabled',
        'thresholdTempBValue',
        'thresholdBilletEnabled',
        'thresholdBilletValue',
        'thresholdBilletTempEnabled',
        'thresholdBilletTempValue',
        'thresholdAtTempEnabled',
        'thresholdAtTempValue',
        'thresholdAtPreEnabled',
        'thresholdAtPreValue',
        'thresholdCountEnabled',
        'thresholdCountValue',
        'thresholdEndPosEnabled',
        'thresholdEndPosValue',
      ],
      'settings-security': ['password'],
    }),
    []
  );
  const settingsSectionHasChanges = useMemo(() => {
    const result: Record<string, boolean> = {};
    Object.entries(settingsSectionFieldMap).forEach(([sectionId, fields]) => {
      if (sectionId === 'settings-summary') {
        result[sectionId] = hasSettingsChanges;
        return;
      }
      result[sectionId] = fields.some((field) => isSettingsFieldDirty(field));
    });
    return result;
  }, [settingsSectionFieldMap, isSettingsFieldDirty, hasSettingsChanges]);

  const buildSettingsSummaryCards = useCallback(() => {
    if (!settingsForm) {
      return [];
    }
    const appliedCount = settingsApplyResult?.applied?.length ?? 0;
    const pendingCount = settingsApplyResult?.pending?.length ?? 0;
    const applyStatus =
      pendingCount > 0 ? '재시작 필요' : appliedCount > 0 ? '즉시 반영' : '저장 전';
    return [
      {
        title: '통신 요약',
        items: [
          `Extruder: ${settingsForm.extruderIp || '-'}:${settingsForm.extruderPort || '-'}`,
          `LS PLC: ${settingsForm.lsIp || '-'}:${settingsForm.lsPort || '-'}`,
        ],
      },
      {
        title: 'SPOT 요약',
        items: [
          `IP: ${settingsForm.spotIp || '-'}`,
          `Refresh: ${settingsForm.spotRefreshInterval || '-'} sec`,
        ],
      },
      {
        title: '저장 요약',
        items: [
          `Log: ${settingsForm.logPath || '-'}`,
          `Snapshot: ${settingsForm.snapshotPath || '-'}`,
        ],
      },
      {
        title: '적용 상태',
        items: [
          `즉시 적용: ${appliedCount}건`,
          `재시작 필요: ${pendingCount}건`,
          `상태: ${applyStatus}`,
        ],
      },
    ];
  }, [settingsForm, settingsApplyResult]);
  const registerSettingsSection = useCallback(
    (id: string) => (element: HTMLDivElement | null) => {
      settingsSectionRefs.current[id] = element;
    },
    []
  );
  const scrollToSettingsSection = useCallback(
    (id: string) => {
      const target = settingsSectionRefs.current[id];
      if (!target) {
        return;
      }
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSettingsSection(id);
    },
    []
  );

  const buildSettingsChangeSummary = useCallback(() => {
    if (!settingsForm || !settingsBaseline) {
      return [] as string[];
    }
    const labelMap: Record<keyof SettingsFormState, string> = {
      extruderIp: 'Extruder IP',
      extruderPort: 'Extruder Port',
      lsIp: 'LS PLC IP',
      lsPort: 'LS PLC Port',
      spotIp: 'SPOT IP',
      spotRefreshInterval: 'SPOT Refresh (sec)',
      thresholdMasterOn: '알림 마스터',
      thresholdSpeedEnabled: '속도 알림 사용',
      thresholdSpeedValue: '속도 임계값',
      thresholdPressEnabled: '압력 알림 사용',
      thresholdPressValue: '압력 임계값',
      thresholdSpotEnabled: 'SPOT 알림 사용',
      thresholdSpotValue: 'SPOT 임계값',
      thresholdTempFEnabled: '컨테이너 앞 알림 사용',
      thresholdTempFValue: '컨테이너 앞 임계값',
      thresholdTempBEnabled: '컨테이너 뒤 알림 사용',
      thresholdTempBValue: '컨테이너 뒤 임계값',
      thresholdBilletEnabled: '빌렛 길이 알림 사용',
      thresholdBilletValue: '빌렛 길이 임계값',
      thresholdBilletTempEnabled: '빌렛 온도 알림 사용',
      thresholdBilletTempValue: '빌렛 온도 임계값',
      thresholdAtTempEnabled: '환경 온도 알림 사용',
      thresholdAtTempValue: '환경 온도 임계값',
      thresholdAtPreEnabled: '환경 습도 알림 사용',
      thresholdAtPreValue: '환경 습도 임계값',
      thresholdCountEnabled: '카운트 알림 사용',
      thresholdCountValue: '카운트 임계값',
      thresholdEndPosEnabled: '종료 위치 알림 사용',
      thresholdEndPosValue: '종료 위치 임계값',
      logPath: 'Log Path',
      snapshotPath: 'Snapshot Path',
      autoSave: '자동 저장',
      rotationEnabled: '로그 회전 사용',
      rotationMode: 'Rotation Mode',
      cycleIdleTime: 'Cycle Idle Time (sec)',
      cycleThresholdPress: 'Cycle Threshold Press',
      password: '설정 비밀번호',
      passwordSet: '비밀번호 설정 상태',
    };

    const formatValue = (value: string | boolean) => {
      if (typeof value === 'boolean') {
        return value ? '사용' : '미사용';
      }
      const trimmed = value.trim();
      return trimmed.length > 0 ? trimmed : '(비어 있음)';
    };

    const keys: Array<keyof SettingsFormState> = [
      'extruderIp',
      'extruderPort',
      'lsIp',
      'lsPort',
      'spotIp',
      'spotRefreshInterval',
      'logPath',
      'snapshotPath',
      'autoSave',
      'rotationEnabled',
      'rotationMode',
      'cycleIdleTime',
      'cycleThresholdPress',
      'password',
    ];

    const summary: string[] = [];

    keys.forEach((key) => {
      if (key === 'password') {
        if (settingsForm.password.trim()) {
          summary.push(`${labelMap.password}: 변경됨`);
        }
        return;
      }
      if (!isSettingsFieldDirty(key)) {
        return;
      }
      const before = formatValue(settingsBaseline[key]);
      const after = formatValue(settingsForm[key]);
      summary.push(`${labelMap[key]}: ${before} → ${after}`);
    });

    return summary;
  }, [settingsForm, settingsBaseline, isSettingsFieldDirty]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }
    const container = settingsScrollRef.current;
    if (!container) {
      return;
    }
    const updateActiveSection = () => {
      const containerTop = container.getBoundingClientRect().top;
      const topOffset = containerTop + 140;
      let currentId = settingsSections[0]?.id ?? '';
      settingsSections.forEach(({ id }) => {
        const section = settingsSectionRefs.current[id];
        if (!section) {
          return;
        }
        const rect = section.getBoundingClientRect();
        if (rect.top <= topOffset) {
          currentId = id;
        }
      });
      if (currentId) {
        setActiveSettingsSection((prev) => (prev !== currentId ? currentId : prev));
      }
    };
    updateActiveSection();
    container.addEventListener('scroll', updateActiveSection);
    window.addEventListener('resize', updateActiveSection);
    return () => {
      container.removeEventListener('scroll', updateActiveSection);
      window.removeEventListener('resize', updateActiveSection);
    };
  }, [settingsOpen, settingsSections]);


  useEffect(() => {
    const fetchSpotConfig = async () => {
      try {
        const res = await axios.get<SpotConfig>(`${API_BASE}/api/spot/config`);
        setSpotConfig(res.data);
      } catch (err) {
        console.error('SPOT config error', err);
      }
    };
    fetchSpotConfig();
  }, []);

  useEffect(() => {
    if (!spotConfig?.image_url) {
      return;
    }
    spotHasImage.current = false;
    setSpotLastSuccessAt(null);
    setSpotImageError(null);
  }, [spotConfig?.image_url]);

  useEffect(() => {
    if (!spotConfig || !spotConfig.image_url) return;
    const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
    const updateImage = () => {
      const separator = spotConfig.image_url.includes('?') ? '&' : '?';
      if (!spotHasImage.current) setSpotImageLoading(true);
      setSpotImageUrl(`${spotConfig.image_url}${separator}t=${Date.now()}`);
    };
    updateImage();
    const timer = setInterval(updateImage, refreshMs);
    return () => clearInterval(timer);
  }, [spotConfig]);

  const handleSpotImageLoaded = () => {
    spotHasImage.current = true;
    setSpotImageLoading(false);
    setSpotImageError(null);
    setSpotLastSuccessAt(Date.now());
  };

  const handleSpotImageError = (message = '이미지 수신 실패') => {
    setSpotImageLoading(false);
    setSpotImageError(message);
  };

  const requestFocus = async (steps: number) => {
    if (!spotConfig?.focus_enabled || focusBusy) return;
    setFocusBusy(true);
    try {
      await axios.post(`${API_BASE}/api/spot/focus`, null, { params: { steps } });
    } catch (err) {
      console.error('SPOT focus error', err);
    } finally {
      setFocusBusy(false);
    }
  };

  // --- Widget Renderers ---
  // --- Scene Creation ---
  // Scene is created once; widget data is read from DataContext.
  const scene = useMemo(() => {
      return getDashboardScene(
         () => <KpiComponent />,
         () => <SpotComponent />,
         () => <TempsComponent />,
         () => <MoldsComponent />,
         () => <EnvComponent />,
         () => <CameraComponent />,
         () => <NoticeComponent />,
         layoutSnapshot?.layout ?? null
      );
  }, [layoutSnapshot]); 

  const layoutRef = useRef<LayoutMap>({});
  const lastRestoreSlotIdRef = useRef<string | null>(null);

  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) {
      return;
    }

    const updateLayoutRef = () => {
      layoutRef.current = buildLayoutMap(grid.state.children);
    };

    updateLayoutRef();
    const sub = grid.subscribeToState(() => updateLayoutRef());
    return () => sub.unsubscribe();
  }, [scene]);

  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) {
      return;
    }
    grid.setState({ isDraggable: layoutEditing, isResizable: layoutEditing });
  }, [scene, layoutEditing]);

  // --- Layout Persistence ---
  const saveLayout = async () => {
    if (!layoutEditing) {
      return;
    }
    const grid = scene.state.body;
    if (grid instanceof SceneGridLayout) {
      layoutRef.current = buildLayoutMap(grid.state.children);
    }
    if (Object.keys(layoutRef.current).length === 0) {
      setLayoutSaveError('레이아웃 정보를 찾을 수 없습니다.');
      return;
    }
    const defaultName =
      layoutSlots.find((slot) => slot.id === layoutActiveId)?.name ??
      `레이아웃 ${Math.min(layoutSlots.length + 1, 3)}`;
    const name = window.prompt('레이아웃 이름을 입력하세요', defaultName);
    if (!name) {
      setLayoutSaveError('저장 취소');
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/layouts`, {
        name,
        layout: layoutRef.current,
        cols: CURRENT_LAYOUT_COLS,
        version: 'v2',
      });
      await loadLayoutSnapshot();
      setLayoutSaveError(null);
      setLayoutSaveMessage('저장됨');
    } catch (error) {
      console.error('Layout save failed', error);
      const message =
        axios.isAxiosError(error) && error.response?.status === 400
          ? '레이아웃은 최대 3개까지 저장할 수 있습니다.'
          : '저장 실패';
      setLayoutSaveError(message);
      return;
    }
    if (saveMessageTimerRef.current !== null) {
      window.clearTimeout(saveMessageTimerRef.current);
    }
    saveMessageTimerRef.current = window.setTimeout(() => {
      setLayoutSaveMessage(null);
      saveMessageTimerRef.current = null;
    }, 2000);
  };

  const restoreLayout = async (slotId?: string | null) => {
    const targetId = slotId ?? lastRestoreSlotIdRef.current;
    if (!targetId) {
      setLayoutRestoreError('복구 대상 없음');
      return;
    }
    lastRestoreSlotIdRef.current = targetId;
    if (!window.confirm('선택한 레이아웃으로 복구하면 현재 배치가 사라집니다. 복구하시겠습니까?')) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/layouts/restore`, { slot_id: targetId });
      await loadLayoutSnapshot();
      setLayoutRestoreError(null);
      setLayoutRestoreMessage('복구됨');
      if (restoreMessageTimerRef.current !== null) {
        window.clearTimeout(restoreMessageTimerRef.current);
      }
      restoreMessageTimerRef.current = window.setTimeout(() => {
        setLayoutRestoreMessage(null);
        restoreMessageTimerRef.current = null;
      }, 2000);
    } catch (error) {
      console.error('Layout restore failed', error);
      setLayoutRestoreError('복구 실패');
    }
  };

  const deleteLayoutSlot = async (slotId?: string | null) => {
    const targetId = slotId ?? null;
    if (!targetId) {
      setLayoutRestoreError('삭제 대상 없음');
      return;
    }
    if (!window.confirm('선택한 레이아웃을 삭제하면 되돌릴 수 없습니다. 삭제하시겠습니까?')) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/layouts/delete`, { slot_id: targetId });
      await loadLayoutSnapshot();
      setLayoutRestoreError(null);
      setLayoutRestoreMessage('삭제됨');
      if (restoreMessageTimerRef.current !== null) {
        window.clearTimeout(restoreMessageTimerRef.current);
      }
      restoreMessageTimerRef.current = window.setTimeout(() => {
        setLayoutRestoreMessage(null);
        restoreMessageTimerRef.current = null;
      }, 2000);
    } catch (error) {
      console.error('Layout delete failed', error);
      setLayoutRestoreError('삭제 실패');
    }
  };

  const ageMs = lastDataAt ? Math.max(0, nowTick - lastDataAt) : null;
  const lastUpdateMs = health?.last_update ? health.last_update * 1000 : null;
  const healthAgeMs = lastUpdateMs ? Math.max(0, nowTick - lastUpdateMs) : null;
  const effectiveAgeMs = healthAgeMs ?? ageMs;
  let statusLabel = 'Offline';
  let statusClass = 'status-offline';
  if (effectiveAgeMs !== null) {
    if (effectiveAgeMs <= STATUS_WARN_MS) {
      statusLabel = 'Running';
      statusClass = 'status-ok';
    } else if (effectiveAgeMs <= STATUS_OFFLINE_MS) {
      statusLabel = 'Warning';
      statusClass = 'status-warn';
    }
  } else if (connected) {
    statusLabel = 'Running';
    statusClass = 'status-ok';
  }
  if (health && (!health.running || !health.thread_alive)) {
    statusLabel = 'Offline';
    statusClass = 'status-offline';
  } else if (health && !health.driver_connected && statusLabel === 'Running') {
    statusLabel = 'Warning';
    statusClass = 'status-warn';
  }
  const latencyText = latencyMs === null ? '--' : `${latencyMs}ms`;
  const ageText = ageMs === null ? '--' : `${Math.round(ageMs)}ms`;
  const avgLatencyText =
    stats?.avg_latency_ms === null || stats?.avg_latency_ms === undefined
      ? '--'
      : `${Math.round(stats.avg_latency_ms)}ms`;
  const errorCountText = stats ? `${stats.error_count}` : '--';
  const lastUpdateText = lastUpdateMs ? formatTime(lastUpdateMs) : '--:--:--';
  const statusTitle = health
    ? `Mode ${health.mode} | Driver ${health.driver_connected ? 'OK' : 'Down'} | Thread ${health.thread_alive ? 'Alive' : 'Stopped'} | Last ${lastUpdateText} | Avg ${avgLatencyText} | Errors ${errorCountText} | Latency ${latencyText} | Age ${ageText}`
    : `Last ${lastUpdateText} | Avg ${avgLatencyText} | Errors ${errorCountText} | Latency ${latencyText} | Age ${ageText}`;
  const commSnapshot = health?.comm;
  const commBadges = useMemo(() => {
    const comm = commSnapshot;
    if (!comm) {
      return [];
    }
    const refreshMs = spotConfig ? Math.max(500, Math.round(spotConfig.refresh_interval * 1000)) : null;
    return [
      buildCommBadge('EX', comm.extruder, nowTick),
      buildCommBadge('LS', comm.ls_plc, nowTick),
      buildSpotCommBadge('SPOT', comm.spot, nowTick, refreshMs),
    ];
  }, [commSnapshot, nowTick, spotConfig]);
  const commDetail = useMemo(() => {
    const refreshMs = spotConfig ? Math.max(500, Math.round(spotConfig.refresh_interval * 1000)) : null;
    return {
      extruder: {
        metrics: commSnapshot?.extruder,
        badge: buildCommBadge('EX', commSnapshot?.extruder, nowTick),
      },
      ls_plc: {
        metrics: commSnapshot?.ls_plc,
        badge: buildCommBadge('LS', commSnapshot?.ls_plc, nowTick),
      },
      spot: {
        metrics: commSnapshot?.spot,
        badge: buildSpotCommBadge('SPOT', commSnapshot?.spot, nowTick, refreshMs),
        refreshMs,
      },
    };
  }, [commSnapshot, nowTick, spotConfig]);
  const commSummaryItems = useMemo(() => {
    const list = [
      { label: 'Extruder', metrics: commDetail.extruder.metrics, badge: commDetail.extruder.badge },
      { label: 'LS PLC', metrics: commDetail.ls_plc.metrics, badge: commDetail.ls_plc.badge },
      { label: 'SPOT', metrics: commDetail.spot.metrics, badge: commDetail.spot.badge },
    ];
    return list.map((item) => {
      const recoverySec = calcRecoverySec(item.metrics);
      return {
        ...item,
        lastError: formatTimeFromSec(item.metrics?.last_error_time ?? null),
        lastOk: formatTimeFromSec(item.metrics?.last_success_time ?? null),
        recovery: formatOptionalSeconds(recoverySec),
      };
    });
  }, [commDetail]);
  const cameraStatus = getCameraStatus({
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
  });

  useEffect(() => {
    if (!statusLabel) {
      return;
    }
    if (statusRef.current === null) {
      statusRef.current = statusLabel;
      return;
    }
    if (statusRef.current === statusLabel) {
      return;
    }
    if (statusLabel === 'Warning') {
      pushNotification('통신 지연', `데이터 갱신 지연: ${ageText}`, 'warn');
    } else if (statusLabel === 'Offline') {
      pushNotification('통신 끊김', '데이터 수신이 중단되었습니다.', 'error');
    } else if (statusLabel === 'Running') {
      pushNotification('통신 정상', '데이터 수신이 정상화되었습니다.', 'info');
    }
    statusRef.current = statusLabel;
  }, [statusLabel, ageText, pushNotification]);

  useEffect(() => {
    if (spotAlertRef.current === false && spotAlertActive) {
      pushNotification('SPOT 경고', 'SPOT 온도 경고 상태입니다.', 'error');
    }
    if (spotAlertRef.current === true && !spotAlertActive) {
      pushNotification('SPOT 정상', 'SPOT 온도가 정상 범위로 복귀했습니다.', 'info');
    }
    spotAlertRef.current = spotAlertActive;
  }, [spotAlertActive, pushNotification]);

  useEffect(() => {
    const type = cameraStatus?.type ?? 'ok';
    if (cameraStatusRef.current === null) {
      cameraStatusRef.current = type;
      return;
    }
    if (cameraStatusRef.current === type) {
      return;
    }
    if (type === 'error' || type === 'danger') {
      pushNotification('카메라 오류', `SPOT 카메라 ${cameraStatus?.title ?? '오류'}`, 'error');
    } else if (type === 'warn') {
      pushNotification('카메라 지연', 'SPOT 카메라 응답이 지연됩니다.', 'warn');
    } else if (type === 'ok' && cameraStatusRef.current !== 'ok') {
      pushNotification('카메라 정상', 'SPOT 카메라가 정상화되었습니다.', 'info');
    }
    cameraStatusRef.current = type;
  }, [cameraStatus, pushNotification]);

  return (
    <div className={`App ${layoutEditing ? 'layout-editing' : ''}`} style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="app-header">
        <h1>{APP_TITLE}</h1>
         <div className="header-controls">
            <div className="status-panel" title={statusTitle}>
              <div className={`status-badge ${statusClass}`}>{statusLabel}</div>
              <div className="status-meta">
                <span className="status-meta-item">
                  <span className="status-meta-label">Last</span>
                  <span className="status-meta-value">{lastUpdateText}</span>
                </span>
                <span className="status-meta-item">
                  <span className="status-meta-label">Avg</span>
                  <span className="status-meta-value">{avgLatencyText}</span>
                </span>
                <span className="status-meta-item">
                  <span className="status-meta-label">Errors</span>
                  <span className="status-meta-value">{errorCountText}</span>
                </span>
              </div>
              {commBadges.length > 0 && (
                <div className="status-comm">
                  {commBadges.map((badge) => (
                    <span
                      key={badge.key}
                      className={`status-comm-item ${badge.state}`}
                      title={badge.title}
                    >
                      {badge.text}
                    </span>
                  ))}
                </div>
              )}
              <div className="status-actions">
                <button
                  className="status-action"
                  onClick={handleReconnect}
                  disabled={reconnectBusy}
                  aria-disabled={reconnectBusy}
                >
                  Reconnect
                </button>
                <button
                  className="status-action"
                  onClick={handleDiagnosis}
                  disabled={diagnosisBusy}
                  aria-disabled={diagnosisBusy}
                >
                  Diagnosis
                </button>
              </div>
            </div>
            <button
              className="notify-bell"
              onClick={() => setNotificationsOpen((prev) => !prev)}
              aria-pressed={notificationsOpen}
            >
              알림
              {unreadCount > 0 && <span className="notify-badge">{unreadCount}</span>}
            </button>
            <div className="menu-wrapper" ref={menuRef}>
              <button
                className="menu-toggle"
                onClick={() => setMenuOpen((prev) => !prev)}
                aria-pressed={menuOpen}
              >
                MENU
              </button>
              <div className={`menu-dropdown ${menuOpen ? 'open' : ''}`}>
                <button
                  className="menu-item"
                  onClick={() => {
                    setLayoutEditing((prev) => !prev);
                  }}
                >
                  {layoutEditing ? '편집 완료' : '편집 모드'}
                </button>
                {layoutEditing ? (
                  <>
                    <button
                      onClick={() => {
                        saveLayout();
                        setMenuOpen(false);
                      }}
                      className="menu-item"
                    >
                      {layoutSaveMessage ?? '레이아웃 저장'}
                    </button>
                    <div className="menu-layout-list">
                      <div className="menu-section-title">저장된 레이아웃</div>
                      {layoutSlots.length > 0 ? (
                        layoutSlots.map((slot) => (
                          <div
                            key={slot.id}
                            className={`menu-layout-row ${slot.id === layoutActiveId ? 'active' : ''}`}
                          >
                            <button
                              className="menu-item menu-layout-button"
                              onClick={() => restoreLayout(slot.id)}
                            >
                              복구
                            </button>
                            <button
                              className="menu-item menu-layout-button menu-layout-delete"
                              onClick={() => deleteLayoutSlot(slot.id)}
                            >
                              삭제
                            </button>
                            <div className="menu-layout-meta">
                              <div className="menu-layout-title">
                                <span className="menu-layout-name">{slot.name}</span>
                                {slot.id === layoutActiveId && (
                                  <span className="menu-layout-active">현재</span>
                                )}
                              </div>
                              <span className="menu-layout-time">{formatMetaTime(slot.updated_at)}</span>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="menu-layout-empty">저장된 레이아웃이 없습니다.</div>
                      )}
                      {layoutRestoreMessage && (
                        <div className="menu-layout-message">{layoutRestoreMessage}</div>
                      )}
                    </div>
                  </>
                ) : null}
                <div className="menu-divider" />
                <button
                  className="menu-item"
                  onClick={() => {
                    setSettingsOpen(true);
                    setMenuOpen(false);
                  }}
                >
                  설정
                </button>
                {layoutEditing && layoutSaveError && (
                  <div className="menu-error">
                    <span>{layoutSaveError}</span>
                    <button onClick={saveLayout} className="retry-button">
                      재시도
                    </button>
                  </div>
                )}
                {layoutEditing && layoutRestoreError && (
                  <div className="menu-error">
                    <span>{layoutRestoreError}</span>
                    <button onClick={restoreLayout} className="retry-button">
                      재시도
                    </button>
                  </div>
                )}
              </div>
            </div>
         </div>
      </header>
      <div className={`notification-drawer ${notificationsOpen ? 'open' : ''}`}>
        <div className="notification-header">
          <span>알림 내역</span>
          <div className="notification-actions">
            <button onClick={clearNotifications} className="notification-action">
              모두 지우기
            </button>
            <button onClick={() => setNotificationsOpen(false)} className="notification-action">
              닫기
            </button>
          </div>
        </div>
        <div className="notification-list">
          {notifications.length === 0 ? (
            <div className="notification-empty">알림이 없습니다.</div>
          ) : (
            notifications.map((item) => (
              <div key={item.id} className={`notification-item ${item.level}`}>
                <div className="notification-item-header">
                  <span className="notification-title">{item.title}</span>
                  <span className="notification-time">
                    {new Date(item.time).toLocaleTimeString()}
                  </span>
                </div>
                <div className="notification-message">{item.message}</div>
              </div>
            ))
          )}
        </div>
      </div>
      {settingsOpen && (
        <div className="settings-backdrop" onClick={() => setSettingsOpen(false)}>
          <div className="settings-modal" onClick={(event) => event.stopPropagation()} ref={settingsScrollRef}>
            <div className="settings-header">
              <span>설정</span>
              <button className="settings-close" onClick={() => setSettingsOpen(false)}>
                닫기
              </button>
            </div>
            <div className="settings-topbar">
              <div className="settings-path" title={settingsConfigPath ?? ''}>
                <span className="settings-path-label">경로</span>
                <span className="settings-path-value">
                  {settingsConfigPath ?? '경로 확인 중'}
                </span>
              </div>
              <div className="settings-badges">
                <span className={`settings-badge ${hasSettingsChanges ? 'warn' : 'ok'}`}>
                  {hasSettingsChanges ? `변경 ${settingsDirtyCount}건` : '변경 없음'}
                </span>
                <span className={`settings-badge ${overrideEnabled ? 'warn' : 'ok'}`}>
                  오버라이드 {overrideEnabled ? 'ON' : 'OFF'}
                </span>
                <span className={`settings-badge ${configReadOnly ? 'warn' : 'ok'}`}>
                  쓰기 {configReadOnly ? '불가' : '가능'}
                </span>
                {settingsRestartRequired && (
                  <span className="settings-badge warn">재시작 필요</span>
                )}
              </div>
              <button
                type="button"
                className="settings-override-toggle"
                onClick={toggleOverride}
                disabled={overrideBusy}
                aria-disabled={overrideBusy}
              >
                {overrideBusy ? '변경 중...' : overrideEnabled ? '오버라이드 끄기' : '오버라이드 켜기'}
              </button>
            </div>
            <div className="settings-sync-row">
              <span className="settings-sync-item">
                버전: {overrideMeta?.version ?? '--'}
              </span>
              <span className="settings-sync-item">
                마지막 동기화: {formatMetaTime(overrideMeta?.last_sync)}
              </span>
              <span className="settings-sync-item">
                소스: {overrideMeta?.source ?? '--'}
              </span>
            </div>
            {settingsLoading && <div className="settings-status">설정 불러오는 중...</div>}
            {settingsError && <div className="settings-error">{settingsError}</div>}
            {configReadOnly && (
              <div className="settings-warning">설정 파일이 읽기 전용입니다. 관리자 권한 또는 파일 속성을 확인하세요.</div>
            )}
            {settingsInfo && <div className="settings-info">{settingsInfo}</div>}
            {settingsToast && (
              <div className={`settings-toast ${settingsToast.level}`}>{settingsToast.message}</div>
            )}
            {externalConfigPending && (
              <div className="settings-external">
                <div className="settings-external-title">외부 변경 감지</div>
                <div className="settings-external-meta">
                  <span>설정 파일이 외부에서 변경되었습니다.</span>
                  <span>감지 시각: {formatTime(externalConfigPendingAt)}</span>
                  <span>새로고침 시 현재 입력 값이 사라집니다.</span>
                </div>
                <div className="settings-external-actions">
                  <button type="button" className="settings-action secondary" onClick={handleExternalRefresh}>
                    새로고침
                  </button>
                  <button type="button" className="settings-action" onClick={handleExternalIgnore}>
                    무시
                  </button>
                </div>
              </div>
            )}
            {settingsForm && (
              <div className="settings-body">
                <div className="settings-nav-select">
                  <label>
                    섹션 선택
                    <select
                      value={activeSettingsSection}
                      onChange={(event) => scrollToSettingsSection(event.target.value)}
                    >
                      {settingsSections.map((section) => (
                        <option key={section.id} value={section.id}>
                          {section.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="settings-nav">
                  <span className="settings-nav-title">섹션</span>
                  {settingsSections.map((section) => (
                    <button
                      key={section.id}
                      type="button"
                      className={`settings-nav-item ${activeSettingsSection === section.id ? 'active' : ''}`}
                      onClick={() => scrollToSettingsSection(section.id)}
                      aria-current={activeSettingsSection === section.id}
                    >
                      <span>{section.label}</span>
                      {settingsSectionHasChanges[section.id] && <span className="settings-nav-dot" />}
                    </button>
                  ))}
                </div>
                <div className="settings-content">
                  <div className="settings-form">
                    <div
                      className="settings-section settings-summary"
                      id="settings-summary"
                      ref={registerSettingsSection('settings-summary')}
                    >
                      <div className="settings-section-title">요약</div>
                      <div className="settings-summary-grid">
                        {buildSettingsSummaryCards().map((card) => (
                          <div key={card.title} className="settings-summary-card">
                            <div className="settings-summary-title">{card.title}</div>
                            <ul className="settings-summary-list">
                              {card.items.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                      <div className="settings-apply-details">
                        <div className="settings-apply-title">적용 상세</div>
                        <div className="settings-apply-grid">
                          <div className="settings-apply-column">
                            <span className="settings-apply-label">즉시 적용</span>
                            {applyDetails.applied.length > 0 ? (
                              <ul className="settings-apply-list">
                                {applyDetails.applied.map((item, index) => (
                                  <li key={`${item}-${index}`}>{item}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="settings-apply-empty">없음</span>
                            )}
                          </div>
                          <div className="settings-apply-column pending">
                            <span className="settings-apply-label">재시작 필요</span>
                            {applyDetails.pending.length > 0 ? (
                              <ul className="settings-apply-list">
                                {applyDetails.pending.map((item, index) => (
                                  <li key={`${item}-${index}`}>{item}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="settings-apply-empty">없음</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="settings-summary-meta">
                        <span>설정 경로: {settingsConfigPath ?? '확인 중'}</span>
                        <span>백업: config.ini.bak 자동 생성</span>
                      </div>
                    </div>
                    <div
                      className="settings-section"
                      id="settings-central"
                      ref={registerSettingsSection('settings-central')}
                    >
                      <div className="settings-section-title">중앙 설정</div>
                      <div className="settings-test-grid">
                        {(() => {
                          const result = centralStatus?.last_result;
                          const badge = getCentralBadge(result?.status, centralStatus?.configured);
                          const statusMessage =
                            result?.message && result.message.trim().length > 0 ? result.message : '상태 정보 없음';
                          return (
                            <div className="settings-test-item">
                              <div className="settings-test-header">
                                <span className="settings-test-title">동기화 상태</span>
                                <span className={`settings-test-badge ${badge.className}`}>{badge.label}</span>
                              </div>
                              <div className="settings-test-meta">
                                <span>연동: {centralStatus?.configured ? '설정됨' : '미설정'}</span>
                                <span>서버: {centralStatus?.server ?? '--'}</span>
                                <span>디바이스: {centralStatus?.device_id ?? '--'}</span>
                                <span>마지막 실행: {formatCentralTime(result)}</span>
                                <span>메시지: {statusMessage}</span>
                              </div>
                              <button
                                type="button"
                                className="settings-test-button"
                                onClick={handleCentralSync}
                                disabled={!centralStatus?.configured || centralSyncBusy}
                                aria-disabled={!centralStatus?.configured || centralSyncBusy}
                              >
                                {centralSyncBusy ? '동기화 중...' : '동기화 실행'}
                              </button>
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                    <div
                      className="settings-section"
                      id="settings-comm"
                      ref={registerSettingsSection('settings-comm')}
                    >
                      <div className="settings-section-title">통신 설정</div>
                      <div className="settings-grid">
                        <label
                          className={`settings-field ${isSettingsFieldDirty('extruderIp') ? 'changed' : ''} ${validationErrors.extruderIp ? 'error' : ''}`}
                        >
                          Extruder IP
                          <input
                            value={settingsForm.extruderIp}
                            onChange={(e) => updateSettingsField('extruderIp', e.target.value)}
                          />
                          {validationErrors.extruderIp && (
                            <span className="settings-field-help error">{validationErrors.extruderIp}</span>
                          )}
                        </label>
                        <label
                          className={`settings-field ${isSettingsFieldDirty('extruderPort') ? 'changed' : ''} ${validationErrors.extruderPort ? 'error' : ''}`}
                        >
                          Extruder Port
                          <input
                            value={settingsForm.extruderPort}
                            onChange={(e) => updateSettingsField('extruderPort', e.target.value)}
                          />
                          {validationErrors.extruderPort && (
                            <span className="settings-field-help error">{validationErrors.extruderPort}</span>
                          )}
                        </label>
                        <label
                          className={`settings-field ${isSettingsFieldDirty('lsIp') ? 'changed' : ''} ${validationErrors.lsIp ? 'error' : ''}`}
                        >
                          LS PLC IP
                          <input
                            value={settingsForm.lsIp}
                            onChange={(e) => updateSettingsField('lsIp', e.target.value)}
                          />
                          {validationErrors.lsIp && (
                            <span className="settings-field-help error">{validationErrors.lsIp}</span>
                          )}
                        </label>
                        <label
                          className={`settings-field ${isSettingsFieldDirty('lsPort') ? 'changed' : ''} ${validationErrors.lsPort ? 'error' : ''}`}
                        >
                          LS PLC Port
                          <input
                            value={settingsForm.lsPort}
                            onChange={(e) => updateSettingsField('lsPort', e.target.value)}
                          />
                          {validationErrors.lsPort && (
                            <span className="settings-field-help error">{validationErrors.lsPort}</span>
                          )}
                        </label>
                        <label
                          className={`settings-field ${isSettingsFieldDirty('spotIp') ? 'changed' : ''} ${validationErrors.spotIp ? 'error' : ''}`}
                        >
                          SPOT IP
                          <input
                            value={settingsForm.spotIp}
                            onChange={(e) => updateSettingsField('spotIp', e.target.value)}
                          />
                          {validationErrors.spotIp && (
                            <span className="settings-field-help error">{validationErrors.spotIp}</span>
                          )}
                        </label>
                        <label
                          className={`settings-field ${isSettingsFieldDirty('spotRefreshInterval') ? 'changed' : ''}`}
                        >
                          SPOT Refresh (sec)
                          <input
                            value={settingsForm.spotRefreshInterval}
                            onChange={(e) => updateSettingsField('spotRefreshInterval', e.target.value)}
                          />
                        </label>
                      </div>
                      <div className="settings-test-grid">
                        {connectionTestTargets
                          .filter((target) => target.key !== 'spot')
                          .map((target) => {
                          const result = connectionTests[target.key];
                          const badge = getTestBadge(result);
                          const targetHasError =
                            target.key === 'extruder'
                              ? Boolean(validationErrors.extruderIp || validationErrors.extruderPort)
                              : Boolean(validationErrors.lsIp || validationErrors.lsPort);
                          return (
                            <div key={target.key} className="settings-test-item">
                              <div className="settings-test-header">
                                <span className="settings-test-title">{target.label}</span>
                                <span className={`settings-test-badge ${badge.className}`}>
                                  {badge.label}
                                </span>
                              </div>
                              <div className="settings-test-meta">
                                <span>최근 테스트: {formatTestTime(result)}</span>
                                {result?.latency_ms !== null && result?.latency_ms !== undefined && (
                                  <span>Latency {result.latency_ms}ms</span>
                                )}
                              </div>
                              {result?.message && <div className="settings-test-message">{result.message}</div>}
              <button
                type="button"
                className="settings-test-button"
                onClick={() => runConnectionTest(target.key)}
                disabled={connectionTestBusy[target.key] || targetHasError}
                aria-disabled={connectionTestBusy[target.key] || targetHasError}
              >
                {connectionTestBusy[target.key] ? '테스트 중...' : '연결 테스트'}
              </button>
              {targetHasError && <div className="settings-test-message">IP/Port 형식을 확인하세요.</div>}
            </div>
                          );
                        })}
                      </div>
                      <div className="settings-comm-metrics">
                        <div className="settings-comm-title">통신 메트릭</div>
                        <div className="settings-comm-log">
                          <div className="settings-comm-log-header">
                            <span className="settings-comm-log-label">메트릭 로그</span>
                            <div className="settings-comm-log-actions">
                              <button
                                type="button"
                                className="settings-comm-log-button"
                                onClick={handleCopyCommLogPath}
                                disabled={!commLogPath}
                                aria-disabled={!commLogPath}
                              >
                                경로 복사
                              </button>
                              <button
                                type="button"
                                className="settings-comm-log-button"
                                onClick={handleOpenCommLogPath}
                                disabled={!commLogPath}
                                aria-disabled={!commLogPath}
                              >
                                폴더 열기
                              </button>
                              <button
                                type="button"
                                className="settings-comm-log-button"
                                onClick={handleOpenCommLogFile}
                                disabled={!commLogPath}
                                aria-disabled={!commLogPath}
                              >
                                파일 열기
                              </button>
                            </div>
                          </div>
                          <span className="settings-comm-log-value">
                            {commLogPath ?? commLogInfoError ?? '--'}
                          </span>
                        </div>
                        {commSnapshot ? (
                          <>
                            <div className="settings-comm-summary">
                              <div className="settings-comm-summary-title">최근 이벤트 요약</div>
                              <div className="settings-comm-summary-grid">
                                {commSummaryItems.map((item) => (
                                  <div key={item.label} className="settings-comm-summary-card">
                                    <div className="settings-comm-summary-header">
                                      <span className="settings-comm-summary-device">{item.label}</span>
                                      <span className={`settings-comm-badge ${item.badge.state}`}>{item.badge.text}</span>
                                    </div>
                                    <div className="settings-comm-summary-body">
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">최근 끊김</span>
                                        <span
                                          className="settings-comm-summary-value"
                                          title={formatOptionalText(item.metrics?.last_error)}
                                        >
                                          {item.lastError}
                                        </span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">최근 복구</span>
                                        <span className="settings-comm-summary-value">{item.lastOk}</span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">복구 시간</span>
                                        <span className="settings-comm-summary-value">{item.recovery}</span>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className="settings-comm-grid">
                            {(() => {
                              const metrics = commDetail.extruder.metrics;
                              const badge = commDetail.extruder.badge;
                              const failureCount =
                                (metrics?.connect_failures ?? 0) + (metrics?.read_failures ?? 0);
                              return (
                                <div className="settings-comm-card">
                                  <div className="settings-comm-header">
                                    <span className="settings-comm-device">Extruder</span>
                                    <span className={`settings-comm-badge ${badge.state}`}>{badge.text}</span>
                                  </div>
                                  <div className="settings-comm-body">
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">연결</span>
                                      <span className="settings-comm-value">
                                        {metrics?.connected ? '연결됨' : '끊김'}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">연결 실패</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.connect_failures)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">읽기 실패</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.read_failures)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">무효 응답</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.invalid_responses)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">스킵</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.skipped_reads)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">실패 합계</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(failureCount)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">백오프</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.backoff_sec)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">다음 재시도</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.next_retry_at ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 성공</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_success_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 오류</span>
                                      <span className="settings-comm-value" title={formatOptionalText(metrics?.last_error)}>
                                        {formatTimeFromSec(metrics?.last_error_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">복구 시간</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.last_recovery_sec ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">블록 병합</span>
                                      <span className="settings-comm-value">
                                        {metrics?.merge_blocks === undefined ? '--' : metrics.merge_blocks ? 'ON' : 'OFF'}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">병합 실패</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.merge_failures)}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })()}
                            {(() => {
                              const metrics = commDetail.ls_plc.metrics;
                              const badge = commDetail.ls_plc.badge;
                              const failureCount =
                                (metrics?.connect_failures ?? 0) + (metrics?.read_failures ?? 0);
                              return (
                                <div className="settings-comm-card">
                                  <div className="settings-comm-header">
                                    <span className="settings-comm-device">LS PLC</span>
                                    <span className={`settings-comm-badge ${badge.state}`}>{badge.text}</span>
                                  </div>
                                  <div className="settings-comm-body">
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">연결</span>
                                      <span className="settings-comm-value">
                                        {metrics?.connected ? '연결됨' : '끊김'}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">연결 실패</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.connect_failures)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">읽기 실패</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.read_failures)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">무효 응답</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.invalid_responses)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">실패 합계</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(failureCount)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">백오프</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.backoff_sec)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">다음 재시도</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.next_retry_at ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 성공</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_success_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 오류</span>
                                      <span className="settings-comm-value" title={formatOptionalText(metrics?.last_error)}>
                                        {formatTimeFromSec(metrics?.last_error_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">복구 시간</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.last_recovery_sec ?? null)}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })()}
                            {(() => {
                              const metrics = commDetail.spot.metrics;
                              const badge = commDetail.spot.badge;
                              const refreshMs = commDetail.spot.refreshMs;
                              return (
                                <div className="settings-comm-card">
                                  <div className="settings-comm-header">
                                    <span className="settings-comm-device">SPOT</span>
                                    <span className={`settings-comm-badge ${badge.state}`}>{badge.text}</span>
                                  </div>
                                  <div className="settings-comm-body">
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 값</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.last_value, 1)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">실패</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.read_failures)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 성공</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_success_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 오류</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_error_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">오류 경과</span>
                                      <span className="settings-comm-value">
                                        {formatAgeSec(metrics?.last_error_time ?? null, nowTick)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">갱신 주기</span>
                                      <span className="settings-comm-value">
                                        {refreshMs ? `${Math.round(refreshMs / 1000)}s` : '--'}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">타임아웃</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.timeout_sec ?? null)}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })()}
                          </div>
                          </>
                        ) : (
                          <div className="settings-comm-empty">통신 메트릭 수집 대기 중입니다.</div>
                        )}
                      </div>
                    </div>

    <div
      className="settings-section"
      id="settings-spot"
      ref={registerSettingsSection('settings-spot')}
    >
      <div className="settings-section-title">SPOT 카메라</div>
      <div className="settings-grid">
        <label
          className={`settings-field ${isSettingsFieldDirty('spotIp') ? 'changed' : ''} ${validationErrors.spotIp ? 'error' : ''}`}
        >
          SPOT IP
          <input
            value={settingsForm.spotIp}
            onChange={(e) => updateSettingsField('spotIp', e.target.value)}
          />
          {validationErrors.spotIp && (
            <span className="settings-field-help error">{validationErrors.spotIp}</span>
          )}
        </label>
        <label
          className={`settings-field ${isSettingsFieldDirty('spotRefreshInterval') ? 'changed' : ''}`}
        >
          SPOT Refresh (sec)
          <input
            value={settingsForm.spotRefreshInterval}
            onChange={(e) => updateSettingsField('spotRefreshInterval', e.target.value)}
          />
        </label>
      </div>
      <div className="settings-spot-preview">
        <div className="settings-spot-status">
          <div className="settings-spot-title">이미지 상태</div>
          <div className="settings-spot-badges">
            {(() => {
              const status = getCameraStatus({
                spotConfig,
                spotImageUrl,
                spotImageLoading,
                spotImageError,
                spotLastSuccessAt,
              });
              if (!status) {
                return <span className="settings-spot-badge ok">정상</span>;
              }
              if (status.type === 'loading') {
                return <span className="settings-spot-badge warn">연결 중</span>;
              }
              if (status.type === 'warn') {
                return <span className="settings-spot-badge warn">지연</span>;
              }
              return <span className="settings-spot-badge error">오류</span>;
            })()}
          </div>
          <div className="settings-spot-meta">
            <span>마지막 수신: {spotLastSuccessAt ? new Date(spotLastSuccessAt).toLocaleTimeString() : '미수신'}</span>
            <span>URL: {spotConfig?.image_url ?? (settingsForm.spotIp ? `http://${settingsForm.spotIp}/image.jpg` : '-')}</span>
          </div>
        </div>
        <div className="settings-spot-frame">
          {spotImageUrl ? (
            <img src={spotImageUrl} alt="SPOT preview" />
          ) : (
            <div className="settings-spot-empty">미리보기 없음</div>
          )}
          {spotImageLoading && (
            <div className="settings-spot-overlay">이미지 로딩 중...</div>
          )}
        </div>
      </div>
    </div>

    <div
      className="settings-section"
      id="settings-storage"
      ref={registerSettingsSection('settings-storage')}
    >
                      <div className="settings-section-title">저장 설정</div>
                      <div className="settings-grid">
                        <label
                          className={`settings-field ${logPathFieldState} ${isSettingsFieldDirty('logPath') ? 'changed' : ''}`}
                        >
                          Log Path
                          <input
                            value={settingsForm.logPath}
                            onChange={(e) => updateSettingsField('logPath', e.target.value)}
                          />
                        </label>
                        <label
                          className={`settings-field ${snapshotPathFieldState} ${isSettingsFieldDirty('snapshotPath') ? 'changed' : ''}`}
                        >
                          Snapshot Path
                          <input
                            value={settingsForm.snapshotPath}
                            onChange={(e) => updateSettingsField('snapshotPath', e.target.value)}
                          />
                        </label>
                        <label
                          className={`settings-field settings-toggle-field ${isSettingsFieldDirty('autoSave') ? 'changed' : ''}`}
                        >
                          <span className="settings-toggle-label">자동 저장 사용</span>
                          <button
                            type="button"
                            className="settings-toggle"
                            aria-pressed={settingsForm.autoSave}
                            onClick={() => updateSettingsField('autoSave', !settingsForm.autoSave)}
                          >
                            <span className="settings-toggle-text">{settingsForm.autoSave ? 'ON' : 'OFF'}</span>
                          </button>
                        </label>
                      </div>
                      <div className="settings-path-health">
                        {(['log', 'snapshot'] as const).map((key) => {
                          const result = pathHealth[key];
                          const badge = getPathBadge(result);
                          const label = key === 'log' ? 'Log Path' : 'Snapshot Path';
                          const pathValue = key === 'log' ? settingsForm.logPath : settingsForm.snapshotPath;
                          return (
                            <div key={key} className="settings-path-card">
                              <div className="settings-path-header">
                                <span className="settings-path-title">{label}</span>
                                <span className={`settings-path-badge ${badge.className}`}>{badge.label}</span>
                              </div>
                              <div className="settings-path-meta">
                                <span>최근 검사: {formatPathCheckTime(result)}</span>
                                {result?.latency_ms !== null && result?.latency_ms !== undefined && (
                                  <span>Latency {result.latency_ms}ms</span>
                                )}
                                {result?.is_network && <span className="settings-path-tag">NAS</span>}
                              </div>
                              <div className="settings-path-message">
                                {formatPathMessage(result)}
                              </div>
                              <div className="settings-path-actions">
                                <button
                                  type="button"
                                  className="settings-path-button"
                                  onClick={() => runPathHealthCheck([{ key, path: pathValue }])}
                                  disabled={pathCheckBusy}
                                  aria-disabled={pathCheckBusy}
                                >
                                  {pathCheckBusy ? '검사 중...' : '검사'}
                                </button>
                                {result?.status === 'WARN' && (
                                  <button
                                    type="button"
                                    className="settings-path-button secondary"
                                    onClick={() => createPath(pathValue)}
                                  >
                                    폴더 생성
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div
                      className="settings-section"
                      id="settings-logging"
                      ref={registerSettingsSection('settings-logging')}
                    >
                      <div className="settings-section-title">로그 회전</div>
                      <div className="settings-grid">
                        <label
                          className={`settings-field settings-toggle-field ${isSettingsFieldDirty('rotationEnabled') ? 'changed' : ''}`}
                        >
                          <span className="settings-toggle-label">로그 회전 사용</span>
                          <button
                            type="button"
                            className="settings-toggle"
                            aria-pressed={settingsForm.rotationEnabled}
                            onClick={() => updateSettingsField('rotationEnabled', !settingsForm.rotationEnabled)}
                          >
                            <span className="settings-toggle-text">{settingsForm.rotationEnabled ? 'ON' : 'OFF'}</span>
                          </button>
                        </label>
                        <label className={`settings-field ${isSettingsFieldDirty('rotationMode') ? 'changed' : ''}`}>
                          Rotation Mode
                          <select
                            value={settingsForm.rotationMode}
                            onChange={(e) => updateSettingsField('rotationMode', e.target.value)}
                          >
                            <option value="BILLET">BILLET</option>
                            <option value="DAILY">DAILY</option>
                          </select>
                          <span className="settings-field-help">
                            BILLET: 빌렛 기준 회전, DAILY: 날짜 기준 분리 저장
                          </span>
                        </label>
                        <label className={`settings-field ${isSettingsFieldDirty('cycleIdleTime') ? 'changed' : ''}`}>
                          Cycle Idle Time (sec)
                          <input
                            value={settingsForm.cycleIdleTime}
                            onChange={(e) => updateSettingsField('cycleIdleTime', e.target.value)}
                          />
                          <span className="settings-field-help">
                            사이클 종료 후 대기 시간(초)
                          </span>
                        </label>
                        <label
                          className={`settings-field ${isSettingsFieldDirty('cycleThresholdPress') ? 'changed' : ''}`}
                        >
                          Cycle Threshold Press
                          <input
                            value={settingsForm.cycleThresholdPress}
                            onChange={(e) => updateSettingsField('cycleThresholdPress', e.target.value)}
                          />
                          <span className="settings-field-help">
                            기준 압력 이상에서 사이클로 판단
                          </span>
                        </label>
                      </div>
                      <div className="settings-hint">
                        로그 회전 기준과 사이클 조건은 CSV 분리 및 저장 주기에 직접 영향을 줍니다.
                      </div>
                    </div>

                    <div
                      className="settings-section"
                      id="settings-alerts"
                      ref={registerSettingsSection('settings-alerts')}
                    >
                      <div className="settings-section-title">알림/임계값</div>
                      <div className="settings-grid">
                        <label
                          className={`settings-field settings-checkbox ${isSettingsFieldDirty('thresholdMasterOn') ? 'changed' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={settingsForm.thresholdMasterOn}
                            onChange={(e) => updateSettingsField('thresholdMasterOn', e.target.checked)}
                          />
                          전체 알림 사용
                        </label>
                      </div>
                      <div className="settings-thresholds">
                        <div className="settings-threshold-header">
                          <span>항목</span>
                          <span>사용</span>
                          <span>임계값</span>
                          <span>단위</span>
                        </div>
                        {thresholdItems.map((item) => {
                          const enabled = settingsForm[item.enableField] as boolean;
                          const value = settingsForm[item.valueField] as string;
                          const error = validationErrors[item.valueField];
                          return (
                            <div key={item.key} className="settings-threshold-row">
                              <span className="settings-threshold-label">{item.label}</span>
                              <label className="settings-threshold-toggle">
                                <input
                                  type="checkbox"
                                  checked={Boolean(enabled)}
                                  onChange={(e) => updateSettingsField(item.enableField, e.target.checked)}
                                />
                                <span>사용</span>
                              </label>
                              <div className="settings-threshold-input">
                                <input
                                  className={error ? 'error' : ''}
                                  value={value}
                                  onChange={(e) => updateSettingsField(item.valueField, e.target.value)}
                                />
                                {error && <span className="settings-field-help error">{error}</span>}
                              </div>
                              <span className="settings-threshold-unit">{item.unit}</span>
                            </div>
                          );
                        })}
                      </div>
                      <div className="settings-hint">
                        알림 사용 여부와 임계값을 함께 설정하세요. 빈 값은 기존 값을 유지합니다.
                      </div>
                    </div>

                    <div
                      className="settings-section"
                      id="settings-security"
                      ref={registerSettingsSection('settings-security')}
                    >
                      <div className="settings-section-title">보안</div>
                      <div className="settings-grid">
                        <label className={`settings-field ${isSettingsFieldDirty('password') ? 'changed' : ''}`}>
                          설정 비밀번호
                          <input
                            type="password"
                            placeholder={settingsForm.passwordSet ? '설정됨' : '미설정'}
                            value={settingsForm.password}
                            onChange={(e) => updateSettingsField('password', e.target.value)}
                          />
                        </label>
                        <div className="settings-hint">
                          비워두면 기존 비밀번호를 유지합니다.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div className="settings-footer">
              <span className="settings-footer-note">
                {configReadOnly
                  ? '설정 파일이 읽기 전용입니다. 관리자 권한/속성을 확인하세요.'
                  : hasValidationError
                    ? '입력값 형식을 확인하세요.'
                    : !overrideEnabled && hasSettingsChanges
                      ? '로컬 오버라이드가 OFF 상태입니다. 저장하려면 먼저 활성화하세요.'
                      : '변경 사항은 재시작 후 적용됩니다.'}
              </span>
              <div className="settings-footer-actions">
                <button
                  className="settings-action secondary"
                  onClick={handleRestoreDefaults}
                  disabled={settingsLoading || configReadOnly || !overrideEnabled}
                  aria-disabled={settingsLoading || configReadOnly || !overrideEnabled}
                >
                  기본값 복원
                </button>
                <button
                  className="settings-action secondary"
                  onClick={handleRestoreBackup}
                  disabled={settingsLoading || configReadOnly || !overrideEnabled}
                  aria-disabled={settingsLoading || configReadOnly || !overrideEnabled}
                >
                  백업 복원
                </button>
                <button className="settings-action secondary" onClick={() => setSettingsOpen(false)}>
                  닫기
                </button>
                <button
                  className="settings-action primary"
                  onClick={handleSaveSettings}
                  disabled={
                    settingsLoading ||
                    pathCheckBusy ||
                    hasPathError ||
                    hasValidationError ||
                    configReadOnly ||
                    (!overrideEnabled && hasSettingsChanges)
                  }
                  aria-disabled={
                    settingsLoading ||
                    pathCheckBusy ||
                    hasPathError ||
                    hasValidationError ||
                    configReadOnly ||
                    (!overrideEnabled && hasSettingsChanges)
                  }
                >
                  저장
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="scene-container" style={{ flexGrow: 1 }}>
        {/* Pass data via context to the scene? 
            Actually, wrapping the Scene Component in a Context Provider works!
            The ReactWidget will be rendered *inside* this provider.
        */}
        <DataContext.Provider
          value={{
            data,
            thresholds: thresholdState,
            spotConfig,
            spotImageUrl,
            spotImageLoading,
            spotImageError,
            spotLastSuccessAt,
            spotAlertActive,
            lastDataAt,
            onSpotImageLoaded: handleSpotImageLoaded,
            onSpotImageError: handleSpotImageError,
            requestFocus,
          }}
        >
           <scene.Component model={scene} />
        </DataContext.Provider>
      </div>
    </div>
  );
}

// --- Context & Components ---
// Define Context to pass data into the Scene's ReactWidgets
type DataContextValue = {
  data: FactoryData | null;
  thresholds: ThresholdState;
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotAlertActive: boolean;
  lastDataAt: number | null;
  onSpotImageLoaded: () => void;
  onSpotImageError: (message?: string) => void;
  requestFocus: (steps: number) => void;
};

const DataContext = React.createContext<DataContextValue>({
  data: null,
  thresholds: buildThresholdStateFromConfig(),
  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotAlertActive: false,
  lastDataAt: null,
  onSpotImageLoaded: () => undefined,
  onSpotImageError: () => undefined,
  requestFocus: () => undefined,
});

const KpiComponent = () => {
  const { data, lastDataAt, thresholds } = React.useContext(DataContext);
  const speedValue = useLastValidNumber(data?.Speed);
  const pressValue = useLastValidNumber(data?.Press);
  const countValue = useLastValidNumber(data?.Count);
  const endPosValue = useLastValidNumber(data?.EndPos);
  
  const missing = !Number.isFinite(data?.Speed) || !Number.isFinite(data?.Press);
  const speedForLogic = speedValue ?? data?.Speed;
  const pressForLogic = pressValue ?? data?.Press;
  const safeSpeed = (typeof speedForLogic === 'number' && Number.isFinite(speedForLogic)) ? speedForLogic : 0;
  const safePress = (typeof pressForLogic === 'number' && Number.isFinite(pressForLogic)) ? pressForLogic : 0;
  const jamCondition = safeSpeed === 0 && safePress >= PRESS_RUNNING_THRESHOLD;
  const jamWarnFallback = useSustainedFlag(jamCondition, ALERT_HOLD_MS);
  const jamDangerFallback = useSustainedFlag(jamCondition, ALERT_HOLD_LONG_MS);
  const computed = data?.Computed;
  const jamLevel = computed?.jam_level;
  const jamWarn = jamLevel ? jamLevel === 'warn' : jamWarnFallback;
  const jamDanger = jamLevel ? jamLevel === 'danger' : jamDangerFallback;
  const speedPercent = calcPercent(safeSpeed, SPEED_MAX);
  const pressPercent = calcPercent(safePress, PRESS_MAX);
  const computedThresholds = computed?.thresholds;
  const speedThresholdHit = computedThresholds?.speed ?? isThresholdHit(thresholds, 'speed', speedValue);
  const pressThresholdHit = computedThresholds?.press ?? isThresholdHit(thresholds, 'press', pressValue);
  const countThresholdHit = computedThresholds?.count ?? isThresholdHit(thresholds, 'count', countValue);
  const endPosThresholdHit = computedThresholds?.endpos ?? isThresholdHit(thresholds, 'endpos', endPosValue);
  const thresholdWarn = speedThresholdHit || pressThresholdHit || countThresholdHit || endPosThresholdHit;

  if (!data) return <div>Loading...</div>;

  const kpiAlertClass = jamDanger ? 'card-danger' : jamWarn || thresholdWarn ? 'card-warning' : '';
  const speedState = mapSpeedLevel(computed?.speed_level) ?? getSpeedState(safeSpeed);
  const pressState = mapPressLevel(computed?.press_level) ?? getPressState(safePress);

  return (
    <div className={`card kpi-card ${kpiAlertClass}`} style={{ height: '100%' }}>
      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">속도</span>
          <div className="kpi-header-meta">
            {speedThresholdHit && <span className="threshold-badge">임계</span>}
            <span className={`kpi-state ${speedState.className}`}>{speedState.label}</span>
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(data.Speed, 1)}</span>
          <span className="kpi-unit">mm/s</span>
        </div>
        <div className="kpi-bar">
          <div className={`kpi-bar-fill ${speedState.className}`} style={{ width: `${speedPercent}%` }} />
        </div>
      </div>

      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">압력</span>
          <div className="kpi-header-meta">
            {pressThresholdHit && <span className="threshold-badge">임계</span>}
            <span className={`kpi-state ${pressState.className}`}>{pressState.label}</span>
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(data.Press, 1)}</span>
          <span className="kpi-unit">bar</span>
        </div>
        <div className="kpi-bar">
          <div className={`kpi-bar-fill ${pressState.className}`} style={{ width: `${pressPercent}%` }} />
        </div>
      </div>

      <div className="kpi-secondary">
        <div className={`kpi-mini ${countThresholdHit ? 'kpi-mini-threshold' : ''}`}>
          <div className="kpi-mini-header">
            <span className="kpi-mini-label">카운트</span>
            {countThresholdHit && <span className="threshold-badge">임계</span>}
          </div>
          <span className="kpi-mini-value">{formatInteger(data.Count)}</span>
        </div>
        <div className={`kpi-mini ${endPosThresholdHit ? 'kpi-mini-threshold' : ''}`}>
          <div className="kpi-mini-header">
            <span className="kpi-mini-label">종료 위치</span>
            {endPosThresholdHit && <span className="threshold-badge">임계</span>}
          </div>
          <div className="kpi-mini-value-row">
            <span className="kpi-mini-value">{formatNumber(data.EndPos, 1)}</span>
            <span className="kpi-mini-unit">mm</span>
          </div>
        </div>
      </div>
      {missing && (
        <div className="missing-note">
          마지막 갱신 {formatTime(lastDataAt)}
        </div>
      )}
    </div>
  );
};

const SpotComponent = () => {
    const { data, spotAlertActive, lastDataAt, thresholds } = React.useContext(DataContext);
    const [sparklineValues, setSparklineValues] = useState<number[]>([]);
    const spotValue = useLastValidNumber(data?.Spot);
    
    const missing = !Number.isFinite(data?.Spot);
    const spotDisplayValue = Number.isFinite(spotValue ?? NaN) ? spotValue! : (data?.Spot ?? NaN);
  const computed = data?.Computed;
  const spotState = mapSpotLevel(computed?.spot_level) ?? getSpotState(spotDisplayValue, spotAlertActive);
  const spotThresholdHit = computed?.thresholds?.spot ?? isThresholdHit(thresholds, 'spot', spotValue);
    const spotPercent = calcPercent(spotDisplayValue, SPOT_MAX_TEMP);
    const { linePath, areaPath, points, thresholdLines } = useMemo(
      () =>
        buildSparklinePaths(
          sparklineValues,
          100,
          60,
          [SPOT_NORMAL_MIN, SPOT_HIGH_MIN, SPOT_WARN_TEMP],
          { min: SPOT_NORMAL_MIN, max: SPOT_WARN_TEMP }
        ),
      [sparklineValues]
    );

    useEffect(() => {
      if (!Number.isFinite(spotDisplayValue)) {
        return;
      }
      setSparklineValues((prev) => {
        const next = [...prev, spotDisplayValue];
        if (next.length > SPARKLINE_POINTS) {
          next.splice(0, next.length - SPARKLINE_POINTS);
        }
        return next;
      });
    }, [spotDisplayValue]);

    if (!data) return <div>Loading...</div>;

    return (
      <div
        className={`card spot-card ${spotState.warning ? 'spot-danger' : spotThresholdHit ? 'spot-threshold' : 'spot-normal'}`}
        style={{ height: '100%' }}
      >
        <div className="spot-gauge">
          <svg viewBox="0 0 200 120" className="spot-gauge-svg" aria-hidden="true">
            <path
              className="spot-gauge-track"
              d="M20 100 A80 80 0 0 1 180 100"
              pathLength={100}
            />
            <path
              className={`spot-gauge-fill ${spotState.fillClass}`}
              d="M20 100 A80 80 0 0 1 180 100"
              pathLength={100}
              strokeDasharray={`${spotPercent} 100`}
            />
          </svg>
          <div className="spot-value">
            <span className="spot-value-number">{formatNumber(spotDisplayValue, 1)}</span>
            <span className="spot-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className="spot-status-row">
          <span className={`spot-status ${spotState.statusClass}`}>
            {spotState.label}
          </span>
          {spotThresholdHit && <span className="threshold-badge">임계</span>}
          {spotState.warning && (
            <span className="spot-alert-icon" aria-label="SPOT 경고">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3L2 21h20L12 3zm0 5.5c.6 0 1 .4 1 1v5c0 .6-.4 1-1 1s-1-.4-1-1v-5c0-.6.4-1 1-1zm0 9c.7 0 1.3.6 1.3 1.3S12.7 20 12 20s-1.3-.6-1.3-1.3S11.3 17.5 12 17.5z" />
              </svg>
            </span>
          )}
        </div>
        <div className={`sparkline ${spotState.sparkClass}`}>
          <svg viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id="spot-sparkline-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="var(--sparkline-color)" stopOpacity="0.35" />
                <stop offset="100%" stopColor="var(--sparkline-color)" stopOpacity="0" />
              </linearGradient>
            </defs>
            {areaPath && <path className="sparkline-area" d={areaPath} />}
            {thresholdLines.map((line) => (
              <line
                key={`thr-${line.value}`}
                className={`sparkline-threshold ${line.value === SPOT_WARN_TEMP ? 'sparkline-threshold-warn' : line.value === SPOT_HIGH_MIN ? 'sparkline-threshold-high' : line.value === SPOT_NORMAL_MIN ? 'sparkline-threshold-normal' : ''}`}
                x1={0}
                y1={line.y}
                x2={100}
                y2={line.y}
              />
            ))}
            {linePath && <path className="sparkline-path" d={linePath} />}
            {points.map((point, index) => (
              <circle
                key={`${point.x}-${point.y}-${index}`}
                className={`sparkline-dot ${index === points.length - 1 ? 'sparkline-dot-last' : ''}`}
                cx={point.x}
                cy={point.y}
                r={index === points.length - 1 ? 3 : 2}
              />
            ))}
          </svg>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const TempsComponent = () => {
    const { data, lastDataAt, thresholds } = React.useContext(DataContext);
    const missing =
      !Number.isFinite(data?.Temp_F) ||
      !Number.isFinite(data?.Temp_B) ||
      !Number.isFinite(data?.Billet_Temp) ||
      !Number.isFinite(data?.Billet_Length);
    const tempFValue = useLastValidNumber(data?.Temp_F);
    const tempBValue = useLastValidNumber(data?.Temp_B);
    const billetTempValue = useLastValidNumber(data?.Billet_Temp);
    const billetLengthValue = useLastValidNumber(data?.Billet_Length);
    const tempFLevel = useThresholdLevel(tempFValue ?? NaN, 350, 450, ALERT_HOLD_MS);
    const tempBLevel = useThresholdLevel(tempBValue ?? NaN, 350, 450, ALERT_HOLD_MS);
    const billetTempLevel = useThresholdLevel(billetTempValue ?? NaN, 440, 480, ALERT_HOLD_MS);
  const computedThresholds = data?.Computed?.thresholds;
  const tempFThresholdHit = computedThresholds?.temp_f ?? isThresholdHit(thresholds, 'temp_f', tempFValue);
  const tempBThresholdHit = computedThresholds?.temp_b ?? isThresholdHit(thresholds, 'temp_b', tempBValue);
  const billetTempThresholdHit =
    computedThresholds?.billet_temp ?? isThresholdHit(thresholds, 'billet_temp', billetTempValue);
  const billetLengthThresholdHit =
    computedThresholds?.billet ?? isThresholdHit(thresholds, 'billet', billetLengthValue);
    
    if (!data) return <div>Loading...</div>;
    const tempFClass = [
      tempFLevel === 'danger' ? 'temp-danger' : tempFLevel === 'warn' ? 'temp-warn' : '',
      tempFThresholdHit ? 'temp-threshold' : '',
    ]
      .filter(Boolean)
      .join(' ');
    const tempBClass = [
      tempBLevel === 'danger' ? 'temp-danger' : tempBLevel === 'warn' ? 'temp-warn' : '',
      tempBThresholdHit ? 'temp-threshold' : '',
    ]
      .filter(Boolean)
      .join(' ');
    const billetTempClass = [
      billetTempLevel === 'danger' ? 'temp-danger' : billetTempLevel === 'warn' ? 'temp-warn' : '',
      billetTempThresholdHit ? 'temp-threshold' : '',
    ]
      .filter(Boolean)
      .join(' ');
    const billetLengthClass = billetLengthThresholdHit ? 'temp-threshold' : '';
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="temp-grid">
          <div className={`temp-tile ${tempFClass}`}>
            <div className="temp-header">
              <span className="temp-label">콘테이너 앞</span>
              {tempFThresholdHit && <span className="threshold-badge">임계</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Temp_F, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${tempBClass}`}>
            <div className="temp-header">
              <span className="temp-label">콘테이너 뒤</span>
              {tempBThresholdHit && <span className="threshold-badge">임계</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Temp_B, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${billetTempClass}`}>
            <div className="temp-header">
              <span className="temp-label">빌렛 온도</span>
              {billetTempThresholdHit && <span className="threshold-badge">임계</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Billet_Temp, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${billetLengthClass}`}>
            <div className="temp-header">
              <span className="temp-label">빌렛 길이</span>
              {billetLengthThresholdHit && <span className="threshold-badge">임계</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Billet_Length, 1)}</span>
              <span className="temp-unit">mm</span>
            </div>
          </div>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const MoldsComponent = () => {
    const { data, lastDataAt } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    const missing =
      !Number.isFinite(data.Mold1) ||
      !Number.isFinite(data.Mold2) ||
      !Number.isFinite(data.Mold3) ||
      !Number.isFinite(data.Mold4) ||
      !Number.isFinite(data.Mold5) ||
      !Number.isFinite(data.Mold6);
  const moldLevels = data?.Computed?.mold_levels;
  const mold1 = mapMoldLevel(moldLevels?.Mold1) ?? getMoldState(data.Mold1).className;
  const mold2 = mapMoldLevel(moldLevels?.Mold2) ?? getMoldState(data.Mold2).className;
  const mold3 = mapMoldLevel(moldLevels?.Mold3) ?? getMoldState(data.Mold3).className;
  const mold4 = mapMoldLevel(moldLevels?.Mold4) ?? getMoldState(data.Mold4).className;
  const mold5 = mapMoldLevel(moldLevels?.Mold5) ?? getMoldState(data.Mold5).className;
  const mold6 = mapMoldLevel(moldLevels?.Mold6) ?? getMoldState(data.Mold6).className;
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="mold-grid">
            <div className={`mold-tile ${mold1}`}>
            <span className="mold-label">Mold 1</span>
            <span className="mold-value">{formatNumber(data.Mold1, 1)}</span>
          </div>
            <div className={`mold-tile ${mold2}`}>
            <span className="mold-label">Mold 2</span>
            <span className="mold-value">{formatNumber(data.Mold2, 1)}</span>
          </div>
            <div className={`mold-tile ${mold3}`}>
            <span className="mold-label">Mold 3</span>
            <span className="mold-value">{formatNumber(data.Mold3, 1)}</span>
          </div>
            <div className={`mold-tile ${mold4}`}>
            <span className="mold-label">Mold 4</span>
            <span className="mold-value">{formatNumber(data.Mold4, 1)}</span>
          </div>
            <div className={`mold-tile ${mold5}`}>
            <span className="mold-label">Mold 5</span>
            <span className="mold-value">{formatNumber(data.Mold5, 1)}</span>
          </div>
            <div className={`mold-tile ${mold6}`}>
            <span className="mold-label">Mold 6</span>
            <span className="mold-value">{formatNumber(data.Mold6, 1)}</span>
          </div>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const EnvComponent = () => {
    const { data, lastDataAt, thresholds } = React.useContext(DataContext);
    const envTempValue = useLastValidNumber(data?.At_Temp);
    const envHumidityValue = useLastValidNumber(data?.At_Pre);
    const tempRaw = data?.At_Temp;
    const humidityRaw = data?.At_Pre;
    const tempDisplay = envTempValue ?? tempRaw ?? NaN;
    const humidityDisplay = envHumidityValue ?? humidityRaw ?? NaN;
    const missing = !Number.isFinite(tempRaw) || !Number.isFinite(humidityRaw);
  const computed = data?.Computed;
  const tempState = mapEnvTempLevel(computed?.env_temp_level) ?? getEnvTempState(tempDisplay);
  const humidityState = mapEnvPreLevel(computed?.env_pre_level) ?? getEnvHumidityState(humidityDisplay);
  const computedThresholds = computed?.thresholds;
  const tempThresholdHit = computedThresholds?.at_temp ?? isThresholdHit(thresholds, 'at_temp', envTempValue);
  const humidityThresholdHit =
    computedThresholds?.at_pre ?? isThresholdHit(thresholds, 'at_pre', envHumidityValue);
    return (
      <div className="card env-card" style={{ height: '100%' }}>
        <div className="env-grid">
          <div className={`env-tile ${tempThresholdHit ? 'env-threshold' : ''}`}>
            <div className="env-header">
              <span className="env-label">환경 온도</span>
              {tempThresholdHit && <span className="threshold-badge">임계</span>}
            </div>
            <div className="env-value-row">
              <span className="env-value">{formatNumber(tempDisplay, 1)}</span>
              <span className="env-unit">{SPOT_UNIT}</span>
            </div>
            <span className={`env-badge ${tempState.className}`}>{tempState.label}</span>
          </div>
          <div className={`env-tile ${humidityThresholdHit ? 'env-threshold' : ''}`}>
            <div className="env-header">
              <span className="env-label">환경 습도</span>
              {humidityThresholdHit && <span className="threshold-badge">임계</span>}
            </div>
            <div className="env-value-row">
              <span className="env-value">{formatNumber(humidityDisplay, 1)}</span>
              <span className="env-unit">%</span>
            </div>
            <span className={`env-badge ${humidityState.className}`}>{humidityState.label}</span>
          </div>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const NoticeComponent = () => {
    const {
      data,
      thresholds,
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
      spotAlertActive,
    } = React.useContext(DataContext);

    const speedValue = useLastValidNumber(data?.Speed);
    const pressValue = useLastValidNumber(data?.Press);
    const spotValue = useLastValidNumber(data?.Spot);
    const tempFValue = useLastValidNumber(data?.Temp_F);
    const tempBValue = useLastValidNumber(data?.Temp_B);
    const billetValue = useLastValidNumber(data?.Billet_Length);
    const billetTempValue = useLastValidNumber(data?.Billet_Temp);
    const envTempValue = useLastValidNumber(data?.At_Temp);
    const envHumValue = useLastValidNumber(data?.At_Pre);
    const countValue = useLastValidNumber(data?.Count);
    const endPosValue = useLastValidNumber(data?.EndPos);

    const cameraStatus = getCameraStatus({
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
    });

    let noticeLevel: 'normal' | 'warning' | 'danger' = 'normal';
    if (spotAlertActive || cameraStatus?.type === 'danger' || cameraStatus?.type === 'error') {
      noticeLevel = 'danger';
    } else if (cameraStatus?.type === 'warn' || cameraStatus?.type === 'loading') {
      noticeLevel = 'warning';
    }

    const noticeMessages: string[] = [];
    const thresholdMessages: string[] = [];

    if (spotAlertActive) {
      noticeMessages.push(`SPOT 온도 ${SPOT_WARN_TEMP}${SPOT_UNIT} 이상 감지`);
    }
    if (cameraStatus) {
      const detail = cameraStatus.detail ? ` (${cameraStatus.detail})` : '';
      noticeMessages.push(`SPOT 카메라 ${cameraStatus.title}${detail}`);
    }
    const computedThresholds = data?.Computed?.thresholds;
    const thresholdHit = (key: ThresholdKey, value: number | null | undefined) => {
      if (computedThresholds && computedThresholds[key] !== undefined) {
        return computedThresholds[key];
      }
      return isThresholdHit(thresholds, key, value);
    };
    if (thresholdHit('speed', speedValue)) thresholdMessages.push(THRESHOLD_LABELS.speed);
    if (thresholdHit('press', pressValue)) thresholdMessages.push(THRESHOLD_LABELS.press);
    if (thresholdHit('spot', spotValue)) thresholdMessages.push(THRESHOLD_LABELS.spot);
    if (thresholdHit('temp_f', tempFValue)) thresholdMessages.push(THRESHOLD_LABELS.temp_f);
    if (thresholdHit('temp_b', tempBValue)) thresholdMessages.push(THRESHOLD_LABELS.temp_b);
    if (thresholdHit('billet', billetValue)) thresholdMessages.push(THRESHOLD_LABELS.billet);
    if (thresholdHit('billet_temp', billetTempValue)) thresholdMessages.push(THRESHOLD_LABELS.billet_temp);
    if (thresholdHit('at_temp', envTempValue)) thresholdMessages.push(THRESHOLD_LABELS.at_temp);
    if (thresholdHit('at_pre', envHumValue)) thresholdMessages.push(THRESHOLD_LABELS.at_pre);
    if (thresholdHit('count', countValue)) thresholdMessages.push(THRESHOLD_LABELS.count);
    if (thresholdHit('endpos', endPosValue)) thresholdMessages.push(THRESHOLD_LABELS.endpos);
    if (thresholdMessages.length > 0) {
      noticeMessages.push(`임계값 초과: ${thresholdMessages.join(', ')}`);
    }
    if (thresholdMessages.length > 0 && noticeLevel === 'normal') {
      noticeLevel = 'warning';
    }
    const noticeClass = noticeLevel === 'danger' ? 'card-danger' : noticeLevel === 'warning' ? 'card-warning' : '';

    return (
      <div className={`card notice-card ${noticeClass}`} style={{ height: '100%' }}>
        <div className="notice-header">
          <span className="notice-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 3L2 21h20L12 3zm0 5.5c.6 0 1 .4 1 1v5c0 .6-.4 1-1 1s-1-.4-1-1v-5c0-.6.4-1 1-1zm0 9c.7 0 1.3.6 1.3 1.3S12.7 20 12 20s-1.3-.6-1.3-1.3S11.3 17.5 12 17.5z" />
            </svg>
          </span>
          <span className="notice-title">{NOTICE_TITLE}</span>
        </div>
        <div className="notice-body">
          {noticeMessages.length > 0 && (
            <ul className="notice-list">
              {noticeMessages.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
          <p className="notice-line">
            {NOTICE_BODY_PREFIX}<b>{NOTICE_TEMP_THRESHOLD}</b>{NOTICE_BODY_SUFFIX}
          </p>
          <p className="notice-line">{NOTICE_FOOTER}</p>
        </div>
      </div>
    );
};

const CameraComponent = () => {
    const {
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
      onSpotImageLoaded,
      onSpotImageError,
      requestFocus,
    } = React.useContext(DataContext);
    if (!spotConfig) return <div>Loading Config...</div>;
    
    // Crosshair logic
    const clamp = (val: number, min: number, max: number) => Math.min(max, Math.max(min, val));
    const cx = clamp(spotConfig.crosshair_x, 0, 1) * spotConfig.widget_width;
    const cy = clamp(spotConfig.crosshair_y, 0, 1) * spotConfig.widget_height;
    const arm = Math.max(1, spotConfig.crosshair_size);
    const gap = Math.max(0, spotConfig.crosshair_gap);
    const thick = Math.max(1, spotConfig.crosshair_thickness);
    const color = spotConfig.crosshair_color || 'lime';

    const lines = [
      { x1: cx - gap, y1: cy, x2: cx - arm, y2: cy },
      { x1: cx + gap, y1: cy, x2: cx + arm, y2: cy },
      { x1: cx, y1: cy - gap, x2: cx, y2: cy - arm },
      { x1: cx, y1: cy + gap, x2: cx, y2: cy + arm },
    ];

    const cameraStatus = getCameraStatus({
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
    });
    
    return (
      <div className="card camera-card" style={{ height: '100%', position: 'relative' }}>
        <div className="camera-frame">
          {spotImageUrl && (
            <img
              className="camera-image"
              src={spotImageUrl}
              alt="SPOT Camera"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onLoad={onSpotImageLoaded}
              onError={() => onSpotImageError()}
            />
          )}
          <svg className="camera-crosshair" viewBox={`0 0 ${spotConfig.widget_width} ${spotConfig.widget_height}`} preserveAspectRatio="none" style={{position:'absolute', top:0, left:0, width:'100%', height:'100%' }}>
            {lines.map((line, idx) => (
              <g key={idx}>
                <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke="black" strokeWidth={thick + 2} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
                <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke={color} strokeWidth={thick} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
              </g>
            ))}
            <circle cx={cx} cy={cy} r={3} stroke="black" strokeWidth={3} fill="none" vectorEffect="non-scaling-stroke" />
            <circle cx={cx} cy={cy} r={3} stroke={color} strokeWidth={1} fill="none" vectorEffect="non-scaling-stroke" />
          </svg>
          {cameraStatus && (
            <div className={`camera-overlay ${cameraStatus.type}`}>
              {cameraStatus.type === 'loading' && <span className="camera-spinner" aria-hidden="true" />}
              <div className="camera-status-text">
                <div className="camera-status-title">{cameraStatus.title}</div>
                {cameraStatus.detail && <div className="camera-status-detail">{cameraStatus.detail}</div>}
              </div>
            </div>
          )}
        </div>
        <div className="camera-controls" style={{marginTop: '4px'}}>
           <button onClick={() => requestFocus(-10)}>FOCUS -</button>
           <button onClick={() => requestFocus(10)}>FOCUS +</button>
        </div>
      </div>
    );
};

export default App;
