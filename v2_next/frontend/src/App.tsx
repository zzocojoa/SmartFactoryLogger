import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { FactoryData, SpotConfig } from './types';
import './App.css';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { getDashboardScene, WidgetType, WidgetRegistry, DashboardItem, DASHBOARD_LAYOUT_KEYS } from './scenes/DashboardScene';
import { SceneDataNode, SceneGridItemLike, SceneGridLayout, SceneGridItem, SceneObjectBase } from '@grafana/scenes';
import { ReactWidget } from './scenes/ReactWidgetObject';
import html2canvas from 'html2canvas';
import { buildSeriesSample } from './timeseries/seriesSampling';
import { SeriesBuffer } from './timeseries/seriesBuffer';
import { buildGroupedFrames, buildTimeSeriesFrame, SeriesFrame } from './timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from './timeseries/seriesCatalog';
import { buildPanelData } from './timeseries/seriesPanelData';
import { buildSeriesThresholds } from './timeseries/seriesThresholds';
import {
  APP_TITLE,
  NOTICE_BODY_PREFIX,
  NOTICE_BODY_SUFFIX,
  NOTICE_FOOTER,
  NOTICE_TEMP_THRESHOLD,
  NOTICE_TITLE,
  SPOT_UNIT,
  LABELS,
  MESSAGES,
  STATUS,
  CONFIG_LABELS,
} from './constants/uiText';
import * as LOGIC from './constants/logic';
import * as THEME from './constants/theme';
import { useModal } from './GlobalModalContext';
import { useTheme } from './ThemeContext';

import { LayoutEditContext } from './LayoutEditContext';

// Initialize Scenes Runtime (guarded for HMR)
if (typeof window !== 'undefined') {
  if (!(window as any).__SCENES_INIT__) {
    initScenesRuntime();
    (window as any).__SCENES_INIT__ = true;
  }
} else {
  initScenesRuntime();
}



// ... (existing imports)

const API_BASE = import.meta.env.VITE_API_BASE_URL || (window.location.protocol.startsWith('file') ? 'http://localhost:8000' : '');

const {
  SPOT_WARN_TEMP,
  SPOT_NORMAL_MIN,
  SPOT_HIGH_MIN,
  SPOT_MAX_TEMP,
  SPARKLINE_POINTS,
  LAYOUT_STORAGE_KEY,
  LAYOUT_BACKUP_KEY,
  SERIES_WINDOW_MINUTES,
} = LOGIC;

const LAYOUT_COLS_KEY = 'grafana_scene_layout_cols';
const LEGACY_LAYOUT_COLS = 24;

const MarkdownWidget = ({ item }: { item: DashboardItem }) => {
  const { layoutEditing } = React.useContext(DataContext);
  const { updateWidget, deleteWidget } = React.useContext(LayoutEditContext);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(item.properties?.content || '');

  useEffect(() => {
    setEditValue(item.properties?.content || '');
  }, [item.properties?.content]);

  const handleSave = () => {
    updateWidget(item.key, { properties: { ...item.properties, content: editValue } });
    setEditing(false);
  };

  return (
    <div className="card notice-card">
      {layoutEditing && (
        <>
          <div className="widget-header-controls">
            <button
              className="widget-control-btn widget-edit-btn"
              onClick={() => setEditing(!editing)}
            >
              {editing ? LABELS.VIEW : LABELS.EDIT}
            </button>
            <button
              className="widget-control-btn widget-delete-btn"
              onClick={() => deleteWidget(item.key)}
              title="위젯 삭제"
            >
              ✕
            </button>
          </div>
        </>
      )}
      <div className="notice-body scrollable">
        {editing ? (
          <div className="notice-editor-container">
            <textarea
              className="notice-textarea"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
            />
            <button className="notice-save-btn" onClick={handleSave}>{LABELS.SAVE}</button>
          </div>
        ) : (
          <div className="notice-content markdown-body">
            <ReactMarkdown>{item.properties?.content || ''}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

const NoticeComponent = ({ item }: { item?: any }) => {
  const { customNotice, setCustomNotice, layoutEditing } = React.useContext(DataContext);
  const { deleteWidget } = React.useContext(LayoutEditContext);
  const modal = useModal();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(customNotice);


  useEffect(() => {
    setEditValue(customNotice);
  }, [customNotice]);

  const handleSave = async () => {
    try {
      await axios.post(`${API_BASE}/api/config/notice`, { content: editValue });
      setCustomNotice(editValue);
      setEditing(false);
    } catch (error) {
      console.error('Failed to save notice', error);
      await modal.alert(MESSAGES.NOTICE_SAVE_FAILURE);
    }
  };

  return (
    <div className="card notice-card">
      
      {layoutEditing && (
        <>
          <div className="widget-header-controls">
            <button
              className="widget-control-btn widget-edit-btn"
              onClick={() => setEditing(!editing)}
            >
              {editing ? LABELS.VIEW : LABELS.EDIT}
            </button>
            {item && (
              <button
                className="widget-control-btn widget-delete-btn"
                onClick={() => deleteWidget(item.key)}
                title={LABELS.DELETE}
              >
                ✕
              </button>
            )}
          </div>
        </>
      )}

      <div className="notice-body">
        {editing ? (
          <div className="notice-editor-container">
            <textarea
              className="notice-textarea"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
            />
            <button className="notice-save-btn" onClick={handleSave}>{LABELS.SAVE}</button>
          </div>
        ) : (
          <div className="notice-content markdown-body">
            <ReactMarkdown>{customNotice || ''}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};


const {
  SERIES_SAMPLES_PER_SEC,
  SERIES_WINDOW_MS,
  SERIES_MAX_POINTS,
  CURRENT_LAYOUT_COLS,
  SPEED_MAX,
  PRESS_MAX,
  PRESS_RUNNING_THRESHOLD,
  ALERT_HOLD_MS,
  ALERT_HOLD_LONG_MS,
  STATUS_WARN_MS,
  STATUS_OFFLINE_MS,
  STATUS_ERROR_RATE_WARN,
  STATUS_P95_WARN_MS,
  STATUS_RECENT_ERROR_MS,
  SETTINGS_AUTO_REFRESH_MS,
  OBSERVABILITY_REFRESH_MS,
  FRONT_ERROR_STORAGE_KEY,
  EXPORT_PATH_STORAGE_KEY,
} = LOGIC;

const APPLY_KEY_LABELS: Record<string, string> = {
  'settings.logpath': CONFIG_LABELS.LOG_PATH,
  'settings.snapshotpath': CONFIG_LABELS.SNAPSHOT_PATH,
  'settings.autosave': CONFIG_LABELS.AUTO_SAVE,
  'settings.password_set': CONFIG_LABELS.PASSWORD_SET,
  'logging.rotation_enabled': CONFIG_LABELS.ROTATION_ENABLED,
  'logging.rotation_mode': CONFIG_LABELS.ROTATION_MODE,
  'logging.cycle_idle_time': CONFIG_LABELS.CYCLE_IDLE,
  'logging.cycle_threshold_press': CONFIG_LABELS.CYCLE_PRESS,
  'logging.csv_header': CONFIG_LABELS.CSV_HEADER,
  'system.intervalsec': CONFIG_LABELS.COLLECT_INTERVAL,
  'spot.ip': CONFIG_LABELS.SPOT_IP,
  'spot.url': CONFIG_LABELS.SPOT_URL,
  'spot.image_url': CONFIG_LABELS.SPOT_IMG_URL,
  'spot.refresh_interval': CONFIG_LABELS.SPOT_REFRESH,
  'spot.crosshair_x': CONFIG_LABELS.SPOT_CROSSHAIR_X,
  'spot.crosshair_y': CONFIG_LABELS.SPOT_CROSSHAIR_Y,
  'spot.crosshair_color': CONFIG_LABELS.SPOT_CROSSHAIR_COLOR,
  'spot.crosshair_thickness': CONFIG_LABELS.SPOT_CROSSHAIR_THICKNESS,
  'spot.crosshair_size': CONFIG_LABELS.SPOT_CROSSHAIR_SIZE,
  'spot.crosshair_gap': CONFIG_LABELS.SPOT_CROSSHAIR_GAP,
  'spot.focus_url': CONFIG_LABELS.SPOT_FOCUS_URL,
  'spot.focus_step': CONFIG_LABELS.SPOT_FOCUS_STEP,
  'spot.actuator_ip': CONFIG_LABELS.SPOT_ACTUATOR_IP,
  'spot.actuator_step': CONFIG_LABELS.SPOT_ACTUATOR_STEP,
  'spot.actuator_url': CONFIG_LABELS.SPOT_ACTUATOR_URL,
  'spot.widget_width': CONFIG_LABELS.SPOT_WIDGET_WIDTH,
  'spot.widget_height': CONFIG_LABELS.SPOT_WIDGET_HEIGHT,
  'extruder.ip': CONFIG_LABELS.EXTRUDER_IP,
  'extruder.port': CONFIG_LABELS.EXTRUDER_PORT,
  'ls_plc.ip': CONFIG_LABELS.LS_PLC_IP,
  'ls_plc.port': CONFIG_LABELS.LS_PLC_PORT,
  'ls_plc.targets': CONFIG_LABELS.LS_PLC_TARGETS,
  'thresholds.enable.master_on': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(마스터)`,
  'thresholds.enable.speed': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.SPEED})`,
  'thresholds.enable.press': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.PRESS})`,
  'thresholds.enable.spot': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.SPOT})`,
  'thresholds.enable.temp_f': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.TEMP_F})`,
  'thresholds.enable.temp_b': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.TEMP_B})`,
  'thresholds.enable.billet': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.BILLET_LEN})`,
  'thresholds.enable.billet_temp': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.BILLET_TEMP})`,
  'thresholds.enable.at_temp': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.ENV_TEMP})`,
  'thresholds.enable.at_pre': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.ENV_HUMID})`,
  'thresholds.enable.count': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.COUNT})`,
  'thresholds.enable.endpos': `${CONFIG_LABELS.THRESHOLD_ENABLE_PREFIX}(${LABELS.END_POS})`,
  'thresholds.values.speed': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.SPEED})`,
  'thresholds.values.press': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.PRESS})`,
  'thresholds.values.spot': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.SPOT})`,
  'thresholds.values.temp_f': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.TEMP_F})`,
  'thresholds.values.temp_b': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.TEMP_B})`,
  'thresholds.values.billet': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.BILLET_LEN})`,
  'thresholds.values.billet_temp': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.BILLET_TEMP})`,
  'thresholds.values.at_temp': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.ENV_TEMP})`,
  'thresholds.values.at_pre': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.ENV_HUMID})`,
  'thresholds.values.count': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.COUNT})`,
  'thresholds.values.endpos': `${CONFIG_LABELS.THRESHOLD_VALUE_PREFIX}(${LABELS.END_POS})`,
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
  recovery_count?: number;
  total_downtime_sec?: number;
  current_downtime_sec?: number;
  last_disconnect_time?: number | null;
  last_recovery_at?: number | null;
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
  window?: {
    window_sec: number;
    request_count: number;
    error_count: number;
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
  };
};

type ObservabilityErrorItem = {
  time: number;
  time_iso?: string;
  source: string;
  message: string;
  detail?: string | null;
  path?: string | null;
  level?: string | null;
  repeat?: number;
};

type ObservabilityErrorsResponse = {
  items: ObservabilityErrorItem[];
  summary: {
    queue_size: number;
    last_error_at?: number | null;
    last_error_source?: string | null;
    last_error_message?: string | null;
    last_error_repeat?: number | null;
  };
};

type FrontendErrorEntry = {
  time: number;
  type: 'error' | 'unhandledrejection';
  message: string;
  detail?: string;
  stack?: string;
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
      custom_notice?: string;
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
  customNotice: string;
};

type ConfigApplyResult = {
  applied?: string[];
  pending?: string[];
};

type ConfigUpdateResponse = {
  ok: boolean;
  restart_required: boolean;
  apply?: ConfigApplyResult;
  meta?: any;
  config?: any;
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
  type?: WidgetType;
  title?: string;
  properties?: any;
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
  return {
    x: typeof raw.x === 'number' ? raw.x : 0,
    y: typeof raw.y === 'number' ? raw.y : 0,
    width: typeof raw.width === 'number' ? raw.width : 4,
    height: typeof raw.height === 'number' ? raw.height : 4,
    type: typeof raw.type === 'string' ? raw.type as WidgetType : undefined,
    title: typeof raw.title === 'string' ? raw.title : undefined,
    properties: raw.properties,
  };
};

const buildLayoutMapFromArray = (items: unknown[]): LayoutMap => {
  const layout: LayoutMap = {};
  (DASHBOARD_LAYOUT_KEYS as unknown as string[]).forEach((key, index) => {
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

const buildLayoutMap = (children: (SceneGridItemLike | SceneObjectBase)[] | undefined): LayoutMap => {
  const next: LayoutMap = {};
  const SCENE_TO_USER = 60 / 24;

  if (!children || !Array.isArray(children)) {
    console.warn('buildLayoutMap: Invalid children', children);
    return next;
  }

  children.forEach((child) => {
    // Duck typing check for SceneGridItem-like state
    const state = (child as any).state;
    if (!state) return;

    const { x, y, width, height, body, key } = state;
    if (!key) return;

    const metadata: { type?: WidgetType; title?: string; properties?: any } = {};
    
    // Check body state for metadata (ReactWidget)
    if (body && body.state) {
        // We look for our specific fields
        const bodyState = body.state;
        if (bodyState.type) metadata.type = bodyState.type as WidgetType;
        if (bodyState.title) metadata.title = bodyState.title;
        if (bodyState.properties) metadata.properties = bodyState.properties;
    }

    next[key] = {
      x: Math.round((x ?? 0) * SCENE_TO_USER),
      y: y ?? 0,
      width: Math.round((width ?? 1) * SCENE_TO_USER),
      height: height ?? 1,
      ...metadata,
    };
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
  const recoveryCount = metrics.recovery_count ?? 0;
  const totalDowntime = metrics.total_downtime_sec ?? null;
  const currentDowntime = metrics.current_downtime_sec ?? null;
  const lastDisconnect = metrics.last_disconnect_time ?? null;
  const lastRecoveryAt = metrics.last_recovery_at ?? null;
  const mergeState = metrics.merge_blocks === undefined ? '' : `Merge ${metrics.merge_blocks ? 'ON' : 'OFF'}`;
  const titleParts = [
    `${key} ${connected ? '연결됨' : '끊김'}`,
    `실패 ${failures}`,
    `백오프 ${backoff}s`,
    `마지막 오류 ${formatTimeFromSec(metrics.last_error_time)}`,
    `오류 후 경과 ${formatAgeSec(metrics.last_error_time ?? null, nowMs ?? null)}`,
    `복구횟수 ${recoveryCount}`,
    `다운타임 ${formatOptionalSeconds(currentDowntime)} / 누적 ${formatOptionalSeconds(totalDowntime)}`,
    `최근 끊김 ${formatTimeFromSec(lastDisconnect)}`,
    `최근 복구 ${formatTimeFromSec(lastRecoveryAt)}`,
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
  const formatted = date.toLocaleString();
  return formatted;
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

const getThresholdValue = (thresholds: ThresholdState, key: ThresholdKey) => {
  if (!thresholds.masterOn) {
    return null;
  }
  const entry = thresholds.entries[key];
  if (!entry?.enabled || entry.value === null) {
    return null;
  }
  return entry.value;
};

const THRESHOLD_LABELS: Record<ThresholdKey, string> = {
  speed: LABELS.SPEED,
  press: LABELS.PRESS,
  spot: LABELS.SPOT,
  temp_f: LABELS.CONTAINER_FRONT,
  temp_b: LABELS.CONTAINER_BACK,
  billet: LABELS.BILLET_LEN,
  billet_temp: LABELS.BILLET_TEMP,
  at_temp: LABELS.ENV_TEMP,
  at_pre: LABELS.ENV_HUMID,
  count: LABELS.COUNT,
  endpos: LABELS.END_POS,
};

const getSpeedState = (speed: number) => {
  if (speed === 0) {
    return { label: '대기', className: 'speed-idle' };
  }
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
  if (press === 0) {
    return { label: '대기', className: 'press-idle' };
  }
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
  idle: { label: '대기', className: 'speed-idle' },
};

const PRESS_LEVEL_MAP: Record<string, { label: string; className: string }> = {
  high: { label: '높음', className: 'press-high' },
  normal: { label: '보통', className: 'press-normal' },
  low: { label: '낮음', className: 'press-low' },
  idle: { label: '대기', className: 'press-idle' },
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
  idle: {
    label: '대기',
    statusClass: 'spot-status-idle',
    fillClass: 'spot-fill-idle',
    warning: false,
    sparkClass: 'sparkline-idle',
  },
};

const mapSpotLevel = (level?: string) => {
  if (!level) return null;
  return SPOT_LEVEL_MAP[level] ?? null;
};

const getSpotState = (temp: number, warningActive: boolean): SpotState => {
  if (!Number.isFinite(temp) || temp === 0) {
    return {
      label: '대기',
      statusClass: 'spot-status-idle',
      fillClass: 'spot-fill-idle',
      warning: false,
      sparkClass: 'sparkline-idle',
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
  const { mode, setMode } = useTheme();
  const modal = useModal();
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const seriesBufferRef = useRef(new SeriesBuffer(SERIES_WINDOW_MS, SERIES_MAX_POINTS));
  const timeSeriesDataNode = useMemo(() => new SceneDataNode(), []);
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [observabilityErrors, setObservabilityErrors] = useState<ObservabilityErrorsResponse | null>(null);
  const [observabilityLoading, setObservabilityLoading] = useState(false);
  const [lastExportPath, setLastExportPath] = useState<string | null>(null);
  const [frontErrors, setFrontErrors] = useState<FrontendErrorEntry[]>([]);
  const [centralStatus, setCentralStatus] = useState<CentralStatus | null>(null);
  
  // Time Series States
  const [seriesWindowMin, setSeriesWindowMin] = useState(30);
  const [seriesPaused, setSeriesPaused] = useState(false);
  const [showThresholds, setShowThresholds] = useState(true);
  const [centralSyncBusy, setCentralSyncBusy] = useState(false);
  const [reconnectBusy, setReconnectBusy] = useState(false);
  const [diagnosisBusy, setDiagnosisBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
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
  const timeSeriesThresholds = useMemo(() => 
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
  , [thresholdConfig, showThresholds]);
  const [settingsRestartRequired, setSettingsRestartRequired] = useState(false);
  const [settingsApplyResult, setSettingsApplyResult] = useState<ConfigApplyResult | null>(null);
  const [settingsPending, setSettingsPending] = useState<ConfigSnapshot['pending'] | null>(null);
  const [settingsPendingBusy, setSettingsPendingBusy] = useState(false);
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
  const [customNotice, setCustomNotice] = useState('');
  const [layoutSaveMessage, setLayoutSaveMessage] = useState<string | null>(null);
  const [layoutSaveError, setLayoutSaveError] = useState<string | null>(null);
  const [layoutRestoreMessage, setLayoutRestoreMessage] = useState<string | null>(null);
  const [layoutRestoreError, setLayoutRestoreError] = useState<string | null>(null);
  const [layoutSnapshot, setLayoutSnapshot] = useState<LayoutSnapshot | null>(null);
  const [, setLayoutLoadError] = useState<string | null>(null);
  const [layoutSlots, setLayoutSlots] = useState<LayoutSlotSummary[]>([]);
  const [layoutActiveId, setLayoutActiveId] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  
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
  const loadFrontErrors = useCallback(() => {
    if (typeof window === 'undefined') {
      return [] as FrontendErrorEntry[];
    }
    try {
      const raw = window.localStorage.getItem(FRONT_ERROR_STORAGE_KEY);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw) as FrontendErrorEntry[];
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed;
    } catch (error) {
      console.error('Front error load failed', error);
      return [];
    }
  }, []);
  const persistFrontErrors = useCallback((items: FrontendErrorEntry[]) => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.localStorage.setItem(FRONT_ERROR_STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      console.error('Front error save failed', error);
    }
  }, []);
  const pushFrontError = useCallback(
    (entry: FrontendErrorEntry) => {
      setFrontErrors((prev) => {
        const next = [entry, ...prev].slice(0, LOGIC.FRONT_ERROR_MAX);
        persistFrontErrors(next);
        return next;
      });
    },
    [persistFrontErrors]
  );
  const clearFrontErrors = useCallback(() => {
    setFrontErrors([]);
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.removeItem(FRONT_ERROR_STORAGE_KEY);
      } catch (error) {
        console.error('Front error clear failed', error);
      }
    }
  }, []);
  const loadExportPath = useCallback(() => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      const stored = window.localStorage.getItem(EXPORT_PATH_STORAGE_KEY);
      if (stored) {
        setLastExportPath(stored);
      }
    } catch (error) {
      console.error('Export path load failed', error);
    }
  }, []);
  const persistExportPath = useCallback((path: string | null) => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      if (path) {
        window.localStorage.setItem(EXPORT_PATH_STORAGE_KEY, path);
      } else {
        window.localStorage.removeItem(EXPORT_PATH_STORAGE_KEY);
      }
    } catch (error) {
      console.error('Export path save failed', error);
    }
  }, []);
  const thresholdState = useMemo(() => {
    if (settingsOpen && settingsForm) {
      return buildThresholdStateFromForm(settingsForm);
    }
    return thresholdConfig;
  }, [settingsOpen, settingsForm, thresholdConfig]);
  const settingsSections = useMemo(
    () => [
      { id: 'settings-summary', label: LABELS.SUMMARY },
      { id: 'settings-central', label: LABELS.CENTRAL_CONFIG },
      { id: 'settings-comm', label: LABELS.COMM_CONFIG },
      { id: 'settings-observability', label: LABELS.OPER_OBSERVABILITY },
      { id: 'settings-spot', label: LABELS.SPOT_CAMERA },
      { id: 'settings-storage', label: LABELS.STORAGE_CONFIG },
      { id: 'settings-logging', label: LABELS.LOG_ROTATION },
      { id: 'settings-alerts', label: LABELS.ALERTS_THRESHOLDS },
      { id: 'settings-security', label: LABELS.SECURITY },
    ],
    []
  );

  useEffect(() => {
    setFrontErrors(loadFrontErrors());
  }, [loadFrontErrors]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handleError = (event: ErrorEvent) => {
      pushFrontError({
        time: Date.now(),
        type: 'error',
        message: event.message || 'Unknown error',
        detail: event.filename ? `${event.filename}:${event.lineno}:${event.colno}` : undefined,
        stack: event.error?.stack,
      });
    };
    const handleRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      let message = 'Unhandled rejection';
      let stack: string | undefined;
      if (reason instanceof Error) {
        message = reason.message;
        stack = reason.stack;
      } else if (reason !== undefined) {
        message = String(reason);
      }
      pushFrontError({
        time: Date.now(),
        type: 'unhandledrejection',
        message,
        detail: 'Promise rejection',
        stack,
      });
    };
    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleRejection);
    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleRejection);
    };
  }, [pushFrontError]);
  const connectionTestTargets = useMemo(
    () => [
      { key: 'extruder' as const, label: CONFIG_LABELS.EXTRUDER },
      { key: 'ls_plc' as const, label: CONFIG_LABELS.LS_PLC },
      { key: 'spot' as const, label: LABELS.SPOT_CAMERA },
    ],
    []
  );
  const thresholdItems = useMemo<ThresholdItem[]>(
    () => [
      {
        key: 'speed',
        label: LABELS.SPEED,
        unit: 'mm/s',
        enableField: 'thresholdSpeedEnabled',
        valueField: 'thresholdSpeedValue',
      },
      {
        key: 'press',
        label: LABELS.PRESS,
        unit: 'bar',
        enableField: 'thresholdPressEnabled',
        valueField: 'thresholdPressValue',
      },
      {
        key: 'spot',
        label: LABELS.SPOT,
        unit: '℃',
        enableField: 'thresholdSpotEnabled',
        valueField: 'thresholdSpotValue',
      },
      {
        key: 'temp_f',
        label: LABELS.CONTAINER_FRONT,
        unit: '℃',
        enableField: 'thresholdTempFEnabled',
        valueField: 'thresholdTempFValue',
      },
      {
        key: 'temp_b',
        label: LABELS.CONTAINER_BACK,
        unit: '℃',
        enableField: 'thresholdTempBEnabled',
        valueField: 'thresholdTempBValue',
      },
      {
        key: 'billet',
        label: LABELS.BILLET_LEN,
        unit: 'mm',
        enableField: 'thresholdBilletEnabled',
        valueField: 'thresholdBilletValue',
      },
      {
        key: 'billet_temp',
        label: LABELS.BILLET_TEMP,
        unit: '℃',
        enableField: 'thresholdBilletTempEnabled',
        valueField: 'thresholdBilletTempValue',
      },
      {
        key: 'at_temp',
        label: LABELS.ENV_TEMP,
        unit: '℃',
        enableField: 'thresholdAtTempEnabled',
        valueField: 'thresholdAtTempValue',
      },
      {
        key: 'at_pre',
        label: LABELS.ENV_HUMID,
        unit: '%',
        enableField: 'thresholdAtPreEnabled',
        valueField: 'thresholdAtPreValue',
      },
      {
        key: 'count',
        label: LABELS.COUNT,
        unit: 'ea',
        enableField: 'thresholdCountEnabled',
        valueField: 'thresholdCountValue',
      },
      {
        key: 'endpos',
        label: LABELS.END_POS,
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
        const sampleTimestamp = Date.now();
        setData(res.data);
        setConnected(true);
        setLastDataAt(sampleTimestamp);
        seriesBufferRef.current.append(buildSeriesSample(res.data, sampleTimestamp));
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

  const timeSeriesFrames = useMemo<Record<string, SeriesFrame> | null>(() => {
    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }
    return buildGroupedFrames(samples, TIME_SERIES_CATALOG, timeSeriesThresholds);
  }, [data, timeSeriesThresholds]);

  const timeSeriesAllFrame = useMemo<SeriesFrame | null>(() => {
    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }
    return buildTimeSeriesFrame(samples, TIME_SERIES_CATALOG, timeSeriesThresholds);
  }, [data, timeSeriesThresholds]);

  useEffect(() => {
    if (!timeSeriesAllFrame) {
      return;
    }
    if (seriesPaused) {
      return;
    }
    const samples = seriesBufferRef.current.getSamples();
    const windowMs = seriesWindowMin * 60 * 1000;
    const panelData = buildPanelData(timeSeriesAllFrame, samples, windowMs);
    timeSeriesDataNode.setState({ data: panelData });
  }, [timeSeriesAllFrame, timeSeriesDataNode, seriesPaused, seriesWindowMin]);

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

  const loadObservabilityErrors = useCallback(
    async (limit: number = LOGIC.OBSERVABILITY_ERROR_LIMIT) => {
      setObservabilityLoading(true);
      try {
        const res = await axios.get<ObservabilityErrorsResponse>(`${API_BASE}/api/observability/errors`, {
          params: { limit },
        });
        setObservabilityErrors(res.data);
      } catch (error) {
        console.error('Observability errors load failed', error);
      } finally {
        setObservabilityLoading(false);
      }
    },
    []
  );

  const fetchLatestExportPath = useCallback(async () => {
    try {
      const res = await axios.get<{ path: string | null }>(`${API_BASE}/api/observability/export/latest`);
      const path = res.data?.path ?? null;
      if (path) {
        setLastExportPath(path);
        persistExportPath(path);
      } else {
        setLastExportPath(null);
        persistExportPath(null);
      }
    } catch (error) {
      console.error('Export path fetch failed', error);
    }
  }, [persistExportPath]);

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
          ? MESSAGES.SYNC_SUCCESS
          : status === 'NO_CHANGE'
            ? MESSAGES.SYNC_NO_CHANGE
            : status === 'SKIPPED'
              ? MESSAGES.SYNC_SKIPPED
              : status === 'DISABLED'
                ? MESSAGES.SYNC_DISABLED
                : MESSAGES.SYNC_FAILURE;
      setSettingsInfo(message);
      await fetchCentralStatus();
      if (settingsOpen) {
        await loadSettings();
      }
    } catch (error) {
      console.error('Central sync failed', error);
      setSettingsError(MESSAGES.SYNC_FAILURE_DETAIL);
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
      await modal.alert('Reconnect requested. Check status badge.');
    } catch (error) {
      console.error('Reconnect failed', error);
      await modal.alert('Reconnect failed.');
    } finally {
      setReconnectBusy(false);
    }
  };

  const handleDiagnosis = async () => {
    if (diagnosisBusy) return;
    setDiagnosisBusy(true);
    try {
      const snapshot = await fetchHealth();
      const statsSnapshot = await fetchStats().catch(() => null);
      const lastUpdate = snapshot.last_update
        ? new Date(snapshot.last_update * 1000).toLocaleString()
        : 'n/a';
      const windowStats = statsSnapshot?.window;
      const errorSummary = statsSnapshot?.errors;
      const windowLine = windowStats
        ? `Window ${windowStats.window_sec}s: req ${windowStats.request_count}, err ${windowStats.error_count}, p95 ${formatOptionalNumber(windowStats.p95_latency_ms)}ms`
        : 'Window: n/a';
      const errorLine = errorSummary
        ? `ErrorQ ${errorSummary.queue_size}, Last ${formatTimeFromSec(errorSummary.last_error_at)}`
        : 'ErrorQ: n/a';
      const detail = [
        `Mode: ${snapshot.mode}`,
        `Driver: ${snapshot.driver_connected ? 'OK' : 'Down'}`,
        `Thread: ${snapshot.thread_alive ? 'Alive' : 'Stopped'}`,
        `Last Update: ${lastUpdate}`,
        windowLine,
        errorLine,
      ].join('\n');
      await modal.alert(detail);
    } catch (error) {
      console.error('Diagnosis failed', error);
      await modal.alert('Diagnosis failed.');
    } finally {
      setDiagnosisBusy(false);
    }
  };

  const handleExportObservability = async () => {
    if (exportBusy) return;
    setExportBusy(true);
    try {
      const res = await axios.post<{ path?: string }>(`${API_BASE}/api/observability/export`, {
        include_errors: true,
        front_errors: frontErrors,
      });
      const path = res.data?.path ?? null;
      if (!path) {
        throw new Error('Export path missing');
      }
      setLastExportPath(path);
      persistExportPath(path);
      await modal.alert(`지표 내보내기 완료:\n${path}`);
    } catch (error) {
      console.error('Observability export failed', error);
      await modal.alert('지표 내보내기 실패.');
    } finally {
      setExportBusy(false);
    }
  };

  const handleOpenObservabilityExportFile = async () => {
    if (!lastExportPath) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/observability/export/open-file`);
    } catch (error) {
      console.error('Open export file failed', error);
      await modal.alert('내보낸 파일 열기 실패.');
    }
  };

  const handleOpenObservabilityExportFolder = async () => {
    if (!lastExportPath) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/observability/export/open-folder`);
    } catch (error) {
      console.error('Open export folder failed', error);
      await modal.alert('내보낸 폴더 열기 실패.');
    }
  };

  const handleCopyObservabilityExportPath = async () => {
    if (!lastExportPath) {
      return;
    }
    try {
      await navigator.clipboard.writeText(lastExportPath);
      await modal.alert('내보낸 경로를 복사했습니다.');
    } catch (error) {
      console.error('Copy export path failed', error);
      await modal.alert('경로 복사 실패');
    }
  };

  const handleClearObservabilityErrors = async () => {
    if (!await modal.confirm('에러 큐를 비우면 복구할 수 없습니다. 비우시겠습니까?')) {
      return;
    }
    try {
      await axios.post(`${API_BASE}/api/observability/errors/clear`);
      await loadObservabilityErrors();
    } catch (error) {
      console.error('Observability clear failed', error);
      await modal.alert('에러 큐 비우기 실패.');
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

  const handleSnapshot = useCallback(async () => {
    if (snapshotLoading) return;
    try {
      setSnapshotLoading(true);
      pushNotification('스냅샷', '스냅샷 생성 및 서버 저장 중...', 'info');
      const element = document.getElementById('root') || document.body;
      const scrollHeight = document.documentElement.scrollHeight;
      
      const canvas = await html2canvas(element, {
        useCORS: true,
        logging: false,
        backgroundColor: '#1E1E1E',
        imageTimeout: 5000,
        height: scrollHeight,
        windowHeight: scrollHeight,
        scrollY: -window.scrollY, 
      } as any);

      const base64Data = canvas.toDataURL('image/png');
      
      try {
        await axios.post(`${API_BASE}/api/control/snapshot`, {
          image_base64: base64Data,
          name: 'snapshot',
          format: 'png'
        });
        pushNotification('스냅샷 성공', '서버 설정 폴더에 저장되었습니다.', 'info');
      } catch (apiError) {
        console.error('Snapshot API failed', apiError);
        pushNotification('스냅샷 실패', '서버 저장 중 오류가 발생했습니다.', 'error');
      }
    } catch (error) {
      console.error('Snapshot capture failed', error);
      pushNotification('스냅샷 실패', '화면 캡처 중 오류가 발생했습니다.', 'error');
    } finally {
      setSnapshotLoading(false);
    }
  }, [pushNotification, snapshotLoading]);

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
      customNotice: values.settings.custom_notice ?? '',
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
      setSettingsPending(snapshot.pending ?? null);
      setOverrideEnabled(Boolean(snapshot.meta?.override_enabled));
      setOverrideMeta(snapshot.meta ?? null);
      if (snapshot.values.settings.custom_notice !== undefined) {
        setCustomNotice(snapshot.values.settings.custom_notice);
      }
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
    setSettingsPending(null);
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
      return;
    }
    loadExportPath();
    fetchLatestExportPath();
    loadObservabilityErrors();
    const interval = window.setInterval(() => {
      loadObservabilityErrors();
    }, OBSERVABILITY_REFRESH_MS);
    return () => window.clearInterval(interval);
  }, [settingsOpen, loadObservabilityErrors, loadExportPath, fetchLatestExportPath]);

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
    if (!settingsForm.customNotice) {
      // errors.customNotice = '내용을 입력하세요.'; // Optional: adding validation for customNotice
    }
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

  const handleExternalRefresh = useCallback(async () => {
    if (!externalConfigPending) {
      return;
    }
    if (hasSettingsChanges) {
      const ok = await modal.confirm('외부 변경 내용을 불러오면 현재 입력 중인 값이 사라집니다. 계속할까요?', {
        variant: 'warning'
      });
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
    // setSettingsInfo('외부 변경 내용을 반영했습니다.'); // Silent mode
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



  // --- Auto Save & Master Toggle Logic ---

  // Auto-dismiss settingsInfo
  useEffect(() => {
    if (settingsInfo) {
      const timer = setTimeout(() => {
        setSettingsInfo(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [settingsInfo]);

  const handleMasterToggle = (checked: boolean) => {
    setSettingsForm((prev) => {
      if (!prev) return prev;
      const next = { ...prev, thresholdMasterOn: checked };
      const fields: (keyof SettingsFormState)[] = [
        'thresholdSpeedEnabled', 'thresholdPressEnabled', 'thresholdSpotEnabled',
        'thresholdTempFEnabled', 'thresholdTempBEnabled',
        'thresholdBilletEnabled', 'thresholdBilletTempEnabled',
        'thresholdAtTempEnabled', 'thresholdAtPreEnabled',
        'thresholdCountEnabled', 'thresholdEndPosEnabled'
      ];
      fields.forEach((field) => {
        (next as any)[field] = checked;
      });
      return next;
    });
  };

  const autoSaveTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const autoSaveEnabled = settingsForm?.autoSave;
    
    if (!autoSaveEnabled || !hasSettingsChanges || settingsLoading || !settingsForm) {
      return;
    }

    if (autoSaveTimerRef.current) {
      window.clearTimeout(autoSaveTimerRef.current);
    }

    autoSaveTimerRef.current = window.setTimeout(() => {
      handleSaveSettings({ auto: true });
    }, 1000); // 1 second debounce

    return () => {
      if (autoSaveTimerRef.current) {
        window.clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [settingsForm, hasSettingsChanges, settingsLoading, settingsForm?.autoSave]);

  const handleSaveSettings = async (options?: { auto?: boolean }) => {
    const isAuto = options?.auto;
    if (!settingsForm) {
      return;
    }
    if (configReadOnly) {
      if (!isAuto) setSettingsError('설정 파일이 읽기 전용입니다. 관리자 권한 또는 파일 속성을 확인하세요.');
      return;
    }
    if (hasValidationError) {
      if (!isAuto) setSettingsError('입력값 형식을 확인하세요.');
      return;
    }
    if (!overrideEnabled && hasSettingsChanges) {
      if (!isAuto) setSettingsError('로컬 오버라이드가 비활성화되어 저장할 수 없습니다.');
      return;
    }
    if (pathCheckBusy) {
      if (!isAuto) setSettingsError('경로 검증이 진행 중입니다.');
      return;
    }
    if (!pathHealth.log || !pathHealth.snapshot) {
      if (!isAuto) {
        setSettingsError('경로 검증이 필요합니다. 검사 버튼을 눌러주세요.');
        runPathHealthCheck();
      }
      return;
    }
    if (hasPathError) {
      if (!isAuto) setSettingsError('저장 경로에 오류가 있습니다. 경로를 수정하세요.');
      return;
    }
    if (!hasSettingsChanges) {
      if (!isAuto) setSettingsInfo('변경 사항이 없습니다.');
      return;
    }

    if (!isAuto) {
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
        custom_notice: settingsForm.customNotice,
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
      const nextMeta = res.data?.meta ?? null;
      const pendingCount = applyInfo?.pending?.length ?? 0;
      const appliedCount = applyInfo?.applied?.length ?? 0;
      if (pendingCount > 0) {
        if (!isAuto) setSettingsInfo('일부 설정은 재시작 후 적용됩니다.');
      } else if (appliedCount > 0) {
        if (!isAuto) setSettingsInfo('설정이 저장되었습니다. 재시작 없이 적용되었습니다.');
      } else {
        if (!isAuto) setSettingsInfo('설정이 저장되었습니다.');
      }
      setSettingsRestartRequired(Boolean(res.data?.restart_required));
      setSettingsApplyResult(applyInfo);
      setSettingsPending(null);
      if (nextMeta) {
        setOverrideMeta(nextMeta);
      }
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
      
      if (!isAuto) {
        pushNotification('설정 저장', notificationMessage, pendingCount > 0 ? 'warn' : 'info');
        showSettingsToast(notificationMessage, pendingCount > 0 ? 'warn' : 'ok');
      }
      setExternalConfigPending(null);
      setExternalConfigPendingAt(null);
      
      // Fetch the latest config snapshot to get the authoritative fingerprint
      // This ensures the polling loop doesn't see our own save as an external change
      try {
        const snapshotRes = await axios.get<ConfigSnapshot>(`${API_BASE}/api/config`);
        const newFingerprint = buildSettingsFingerprint(snapshotRes.data);
        settingsFingerprintRef.current = newFingerprint;
      } catch (ignore) {
        // If snapshot fetch fails, we just risk an extra notification, which is acceptable
      }

      settingsExternalNotifyRef.current = null;
    } catch (error) {
      console.error('Config save failed', error);
      if (!isAuto) {
        setSettingsError('설정 저장에 실패했습니다.');
        pushNotification('설정 저장 실패', '설정 저장에 실패했습니다.', 'error');
        showSettingsToast('설정 저장 실패', 'error');
      } else {
        console.error('[AutoSave] Save failed', error);
      }
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
    if (!await modal.confirm('기본값으로 복원하시겠습니까?', { variant: 'warning' })) {
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
    if (!await modal.confirm('백업 파일(config.ini.bak)로 복원하시겠습니까?', { variant: 'warning' })) {
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

  const handlePendingApply = async () => {
    if (settingsLoading || settingsPendingBusy) {
      return;
    }
    if (!settingsPending) {
      setSettingsError('보류된 설정이 없습니다.');
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
    if (!await modal.confirm('보류된 설정을 다시 적용하시겠습니까?')) {
      return;
    }
    setSettingsPendingBusy(true);
    setSettingsError(null);
    try {
      await axios.post(`${API_BASE}/api/config/pending/apply`);
      await loadSettings();
      showSettingsToast('보류된 설정을 적용했습니다.', 'ok');
    } catch (error) {
      console.error('Pending apply failed', error);
      setSettingsError('보류된 설정 적용에 실패했습니다.');
      showSettingsToast('보류된 설정 적용 실패', 'error');
    } finally {
      setSettingsPendingBusy(false);
    }
  };

  const handlePendingClear = async () => {
    if (settingsLoading || settingsPendingBusy) {
      return;
    }
    if (!settingsPending) {
      setSettingsError('보류된 설정이 없습니다.');
      return;
    }
    if (!await modal.confirm('보류된 설정을 삭제하시겠습니까?', { variant: 'warning' })) {
      return;
    }
    setSettingsPendingBusy(true);
    setSettingsError(null);
    try {
      await axios.post(`${API_BASE}/api/config/pending/clear`);
      await loadSettings();
      showSettingsToast('보류된 설정을 삭제했습니다.', 'ok');
    } catch (error) {
      console.error('Pending clear failed', error);
      setSettingsError('보류된 설정 삭제에 실패했습니다.');
      showSettingsToast('보류된 설정 삭제 실패', 'error');
    } finally {
      setSettingsPendingBusy(false);
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
      const input = await modal.prompt('로컬 오버라이드 변경을 위해 비밀번호를 입력하세요.', undefined, { variant: 'warning' });
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
    } catch (error) {
      console.error('Override toggle failed', error);
      const message = axios.isAxiosError(error) ? (error.response?.data?.detail || error.message) : String(error);
      setSettingsError(`오버라이드 변경 실패: ${message}`);
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
        Object.entries(results).forEach(([key, val]) => {
          if (key === 'log' || key === 'snapshot') {
            const value = val as PathHealthResult;
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
      'settings-observability': [],
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
      result[sectionId] = fields.some((field) => isSettingsFieldDirty(field as keyof SettingsFormState));
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
    const lastSavedText = formatMetaTime(overrideMeta?.last_sync);
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
          `최근 저장: ${lastSavedText}`,
          `상태: ${applyStatus}`,
        ],
      },
    ];
  }, [settingsForm, settingsApplyResult, overrideMeta]);
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
      customNotice: '작업자 공지사항',
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
      const containerRect = container.getBoundingClientRect();
      const triggerY = 100; // Adjusted visual trigger point
      let currentId = settingsSections[0]?.id ?? '';

      settingsSections.forEach(({ id }) => {
        const section = settingsSectionRefs.current[id];
        if (!section) return;
        
        const rect = section.getBoundingClientRect();
        const relativeTop = rect.top - containerRect.top;
        
        if (relativeTop <= triggerY) {
          currentId = id;
        }
      });
      
      if (currentId) {
        setActiveSettingsSection((prev) => (prev !== currentId ? currentId : prev));
      }
    };
    updateActiveSection();
    container.addEventListener('scroll', updateActiveSection, { passive: true });
    window.addEventListener('resize', updateActiveSection);
    return () => {
      container.removeEventListener('scroll', updateActiveSection);
      window.removeEventListener('resize', updateActiveSection);
    };
  }, [settingsOpen, settingsSections, settingsForm]);


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
      setSpotImageUrl(`${API_BASE}/api/spot/proxy_image?t=${Date.now()}`);
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
      pushNotification('초점 조절 실패', 'SPOT 액추에이터 제어 중 오류가 발생했습니다.', 'error');
    } finally {
      setFocusBusy(false);
    }
  };

  // --- Widget Renderers ---
  // --- Scene Creation ---
  // Scene is created once; widget data is read from DataContext.
  const scene = useMemo(() => {
     const registry: WidgetRegistry = {
       kpi: () => <KpiComponent />,
       spot: () => <SpotComponent />,
       temps: () => <TempsComponent />,
       molds: () => <MoldsComponent />,
       env: () => <EnvComponent />,
       camera: () => <CameraComponent />,
       notice: (item) => <NoticeComponent item={item} />,
       timeseries: () => <TimeSeriesWidget />,
       markdown: (item) => <MarkdownWidget item={item} />,
     };
     return getDashboardScene(registry, layoutSnapshot?.layout ?? null);
  }, [layoutSnapshot, timeSeriesDataNode, customNotice]);
 // timeSeriesDataNode dep might need removal if unused 

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
    const name = await modal.prompt('레이아웃 이름을 입력하세요', defaultName);
    if (!name) {
      setLayoutSaveError('저장 취소');
      pushNotification('레이아웃 저장', '저장이 취소되었습니다.', 'warn');
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
      pushNotification('레이아웃 저장', `저장 완료: ${name}`, 'info');
    } catch (error) {
      console.error('Layout save failed', error);
      const message =
        axios.isAxiosError(error) && error.response?.status === 400
          ? '레이아웃은 최대 3개까지 저장할 수 있습니다.'
          : '저장 실패';
      setLayoutSaveError(message);
      pushNotification('레이아웃 저장 실패', message, 'error');
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
    if (!await modal.confirm('선택한 레이아웃으로 복구하면 현재 배치가 사라집니다. 복구하시겠습니까?', { variant: 'warning' })) {
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

  const handleAddWidget = (type: WidgetType) => {
    const newKey = `${type}-${Date.now()}`;
    setLayoutSnapshot((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        layout: {
          ...prev.layout,
          [newKey]: {
            x: 0,
            y: 0, // Put at top
            width: 20,
            height: 6,
            type,
            title: type === 'markdown' ? 'New Memo' : '새 위젯',
          },
        },
      };
    });
    setMenuOpen(false);
  };

  const deleteLayoutSlot = async (slotId: string) => {
    const targetId = slotId;
    if (!targetId) {
      setLayoutRestoreError('삭제 대상 없음');
      return;
    }
    if (!await modal.confirm('선택한 레이아웃을 삭제하면 되돌릴 수 없습니다. 삭제하시겠습니까?', { variant: 'error' })) {
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

  const handleRemoveWidget = (key: string) => {
    // if (!window.confirm('위젯을 삭제하시겠습니까?')) return;
    setLayoutSnapshot((prev) => {
        if (!prev) return prev;
        const newLayout = { ...prev.layout };
        if (key in newLayout) {
             delete newLayout[key];
        }
        return { ...prev, layout: newLayout };
    });
  };

  const handleUpdateWidget = (key: string, updates: any) => {
    // Capture current visual state (positions) to prevent reset
    const currentPositions = layoutRef.current;

    setLayoutSnapshot((prev) => {
      if (!prev) return prev;
      const newLayout = { ...prev.layout };
      
      // Update items with current visual positions
      if (currentPositions && Object.keys(currentPositions).length > 0) {
        Object.keys(newLayout).forEach((k) => {
           if (currentPositions[k]) {
             newLayout[k] = { ...newLayout[k], ...currentPositions[k] };
           }
        });
      }

      // Apply the specific update
      if (newLayout[key]) {
          newLayout[key] = { ...newLayout[key], ...updates };
      }
      return { ...prev, layout: newLayout };
    });
  };

  const ageMs = lastDataAt ? Math.max(0, nowTick - lastDataAt) : null;
  const lastUpdateMs = health?.last_update ? health.last_update * 1000 : null;
  const healthAgeMs = lastUpdateMs ? Math.max(0, nowTick - lastUpdateMs) : null;
  const effectiveAgeMs = healthAgeMs ?? ageMs;
  const statsWindow = stats?.window;
  const windowRequestCount = statsWindow?.request_count ?? 0;
  const windowErrorRate = statsWindow?.error_rate ?? null;
  const windowErrorCount = statsWindow?.error_count ?? null;
  const windowP95 = statsWindow?.p95_latency_ms ?? null;
  const errorQueueSize = stats?.errors?.queue_size ?? null;
  const lastErrorAt = stats?.errors?.last_error_at ?? null;
  const lastErrorAgeMs = lastErrorAt ? Math.max(0, nowTick - lastErrorAt * 1000) : null;
  const hasRecentError =
    lastErrorAgeMs !== null && lastErrorAgeMs <= STATUS_RECENT_ERROR_MS;
  const hasWindowIssue =
    windowRequestCount >= 5 &&
    ((windowErrorRate !== null && windowErrorRate >= STATUS_ERROR_RATE_WARN) ||
      (windowP95 !== null && windowP95 >= STATUS_P95_WARN_MS) ||
      (windowErrorCount !== null && windowErrorCount >= 3));
  const commSeverity = (() => {
    const comm = health?.comm;
    if (!comm) {
      return 'idle';
    }
    const refreshMs = spotConfig ? Math.max(500, Math.round(spotConfig.refresh_interval * 1000)) : null;
    const states = [
      buildCommBadge('EX', comm.extruder, nowTick).state,
      buildCommBadge('LS', comm.ls_plc, nowTick).state,
      buildSpotCommBadge('SPOT', comm.spot, nowTick, refreshMs).state,
    ];
    if (states.includes('error')) return 'error';
    if (states.includes('warn')) return 'warn';
    return 'ok';
  })();
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
  } else if (statusLabel === 'Running') {
    if (commSeverity === 'error' || commSeverity === 'warn' || hasWindowIssue || hasRecentError) {
      statusLabel = 'Warning';
      statusClass = 'status-warn';
    }
  }
  const latencyText = latencyMs === null ? '--' : `${latencyMs}ms`;
  const ageText = ageMs === null ? '--' : `${Math.round(ageMs)}ms`;
  const avgLatencyText =
    stats?.avg_latency_ms === null || stats?.avg_latency_ms === undefined
      ? '--'
      : `${Math.round(stats.avg_latency_ms)}ms`;
  const errorCountText = stats ? `${stats.error_count}` : '--';
  const windowP95Text = windowP95 === null || windowP95 === undefined ? '--' : `${Math.round(windowP95)}ms`;
  const errorQueueText = errorQueueSize === null ? '--' : `${errorQueueSize}`;
  const lastUpdateText = lastUpdateMs ? formatTime(lastUpdateMs) : '--:--:--';
  const windowSummaryText = statsWindow
    ? `Win ${statsWindow.window_sec}s req ${statsWindow.request_count}, err ${statsWindow.error_count}, p95 ${windowP95Text}`
    : 'Win --';
  const errorSummaryText = lastErrorAt
    ? `ErrQ ${errorQueueText}, last ${formatTimeFromSec(lastErrorAt)}`
    : `ErrQ ${errorQueueText}`;
  const statusTitle = health
    ? `Mode ${health.mode} | Driver ${health.driver_connected ? 'OK' : 'Down'} | Thread ${health.thread_alive ? 'Alive' : 'Stopped'} | Last ${lastUpdateText} | Avg ${avgLatencyText} | Errors ${errorCountText} | Latency ${latencyText} | Age ${ageText} | ${windowSummaryText} | ${errorSummaryText}`
    : `Last ${lastUpdateText} | Avg ${avgLatencyText} | Errors ${errorCountText} | Latency ${latencyText} | Age ${ageText} | ${windowSummaryText} | ${errorSummaryText}`;
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
      const channelMetrics =
        item.metrics && 'backoff_sec' in item.metrics ? (item.metrics as CommChannelMetrics) : undefined;
      return {
        ...item,
        lastError: formatTimeFromSec(item.metrics?.last_error_time ?? null),
        lastOk: formatTimeFromSec(item.metrics?.last_success_time ?? null),
        recovery: formatOptionalSeconds(recoverySec),
        recoveryCount: formatOptionalNumber(channelMetrics?.recovery_count),
        totalDowntime: formatOptionalSeconds(channelMetrics?.total_downtime_sec ?? null),
        currentDowntime: formatOptionalSeconds(channelMetrics?.current_downtime_sec ?? null),
        lastDisconnect: formatTimeFromSec(channelMetrics?.last_disconnect_time ?? null),
        lastRecoveryAt: formatTimeFromSec(channelMetrics?.last_recovery_at ?? null),
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
                <span className="status-meta-item">
                  <span className="status-meta-label">ErrQ</span>
                  <span className="status-meta-value">{errorQueueText}</span>
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
              </div>
              
              <div style={{ marginLeft: '16px', paddingLeft: '16px', borderLeft: '1px solid var(--border-muted)' }}>
                 <button
                    className={`status-action ${snapshotLoading ? 'loading' : ''}`}
                    onClick={handleSnapshot}
                    disabled={snapshotLoading}
                    aria-disabled={snapshotLoading}
                    title={settingsForm?.snapshotPath ? `Save to: ${settingsForm.snapshotPath}` : 'Snapshot'}
                  >
                    Snapshot
                  </button>
              </div>

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

            
            {/* Removed Series Controls from Header */}
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
                    <div className="menu-divider" />
                    <div className="menu-dropdown-section">
                      <div className="menu-section-title">위젯 추가</div>
                      <button
                        className="menu-item"
                        onClick={() => handleAddWidget('markdown')}
                      >
                        New Memo
                      </button>
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
                    <button onClick={() => restoreLayout()} className="retry-button">
                      재시도
                    </button>
                  </div>
                )}
                
                <div style={{ margin: '8px 0', borderBottom: '1px solid var(--border-muted)' }} />
                <div className="menu-section-title" style={{ padding: '4px 12px', fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>테마 설정</div>
                <div style={{ padding: '0 12px 12px 12px', display: 'flex', gap: '8px' }}>
                  <button
                    className={`custom-modal-btn ${mode === 'light' ? 'confirm' : 'cancel'}`}
                    onClick={() => setMode('light')}
                    style={{ flex: 1, padding: '6px 0', fontSize: '0.8rem', justifyContent: 'center' }}
                  >
                    Light
                  </button>
                  <button
                    className={`custom-modal-btn ${mode === 'dark' ? 'confirm' : 'cancel'}`}
                    onClick={() => setMode('dark')}
                    style={{ flex: 1, padding: '6px 0', fontSize: '0.8rem', justifyContent: 'center' }}
                  >
                    Dark
                  </button>
                  <button
                    className={`custom-modal-btn ${mode === 'auto' ? 'confirm' : 'cancel'}`}
                    onClick={() => setMode('auto')}
                    style={{ flex: 1, padding: '6px 0', fontSize: '0.8rem', justifyContent: 'center' }}
                  >
                    Auto
                  </button>
                </div>
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
          <div className="settings-modal" onClick={(event) => event.stopPropagation()}>
            <div className="settings-header">
              <span className="settings-header-title">설정</span>
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
            {settingsForm && (<>
                  <div className="settings-content-wrapper">
                  <div className="settings-nav">
                    <span className="settings-nav-title">Menu</span>
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
                  <div className="settings-content" ref={settingsScrollRef}>
                    <div className="settings-form">
                      {/* Summary Section */}
                      <div
                        className="settings-section settings-summary"
                        id="settings-summary"
                        ref={registerSettingsSection('settings-summary')}
                      >
                        <div className="settings-section-title">{LABELS.SUMMARY_INFO}</div>
                        <div className="settings-summary-grid">
                          {buildSettingsSummaryCards()
                            .sort((a, b) => {
                              const order = ['통신 요약', '저장 요약', 'SPOT 요약'];
                              const ia = order.indexOf(a.title);
                              const ib = order.indexOf(b.title);
                              // Put known items first in order, unknowns last
                              if (ia === -1 && ib === -1) return 0;
                              if (ia === -1) return 1;
                              if (ib === -1) return -1;
                              return ia - ib;
                            })
                            .map((card) => {
                            const isWide = ['통신 요약', '저장 요약'].includes(card.title);
                            return (
                              <div key={card.title} className={`settings-summary-card ${isWide ? 'wide' : ''}`}>
                              <div className="settings-summary-title">{card.title}</div>
                              <ul className="settings-summary-list">
                                {card.items.map((item) => (
                                  <li key={item}>
                                    <div className="settings-summary-value" title={item}>
                                      {item}
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ); })}
                        </div>
                      <div className="settings-apply-details">
                        <div className="settings-apply-title">{LABELS.APPLY_DETAIL}</div>
                        <div className="settings-apply-grid">
                          <div className="settings-apply-column">
                            <span className="settings-apply-label">{LABELS.IMMEDIATE_APPLY}</span>
                            {applyDetails.applied.length > 0 ? (
                              <ul className="settings-apply-list">
                                {applyDetails.applied.map((item, index) => (
                                  <li key={`${item}-${index}`}>{item}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="settings-apply-empty">{LABELS.NONE}</span>
                            )}
                          </div>
                          <div className="settings-apply-column pending">
                            <span className="settings-apply-label">{LABELS.RESTART_REQUIRED}</span>
                            {applyDetails.pending.length > 0 ? (
                              <ul className="settings-apply-list">
                                {applyDetails.pending.map((item, index) => (
                                  <li key={`${item}-${index}`}>{item}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="settings-apply-empty">{LABELS.NONE}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      {settingsPending && (
                        <div className="settings-pending-card">
                          <div className="settings-pending-header">
                            <span className="settings-pending-title">{LABELS.PENDING_SAVE}</span>
                            <span className="settings-pending-badge">{LABELS.PENDING}</span>
                          </div>
                          <div className="settings-pending-meta">
                            <span>{LABELS.CREATED}: {formatMetaTime(settingsPending.created_at)}</span>
                            <span>{LABELS.SOURCE}: {settingsPending.source ?? 'local'}</span>
                            <span>{LABELS.REASON}: {settingsPending.reason ?? '저장 실패'}</span>
                            <span>{LABELS.PATH}: {settingsPending.path ?? '-'}</span>
                          </div>
                          <div className="settings-pending-actions">
                            <button
                              type="button"
                              className="settings-action warn"
                              onClick={handlePendingApply}
                              disabled={settingsPendingBusy}
                              aria-disabled={settingsPendingBusy}
                            >
                              {LABELS.APPLY_PENDING}
                            </button>
                            <button
                              type="button"
                              className="settings-action ghost"
                              onClick={handlePendingClear}
                              disabled={settingsPendingBusy}
                              aria-disabled={settingsPendingBusy}
                            >
                              {LABELS.DELETE_PENDING}
                            </button>
                          </div>
                        </div>
                      )}
                      <div className="settings-summary-meta">
                        <span>{LABELS.CONFIG_PATH}: {settingsConfigPath ?? LABELS.SYNCING}</span>
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
                                <span>{LABELS.CENTRAL_CONFIG}: {centralStatus?.configured ? STATUS.SET : STATUS.NOT_SET}</span>
                                <span>{LABELS.SERVER}: {centralStatus?.server ?? '--'}</span>
                                <span>{LABELS.DEVICE}: {centralStatus?.device_id ?? '--'}</span>
                                <span>{LABELS.LAST_RUN}: {formatCentralTime(result)}</span>
                                <span>{LABELS.MESSAGE}: {statusMessage}</span>
                              </div>
                              <button
                                type="button"
                                className="settings-test-button"
                                onClick={handleCentralSync}
                                disabled={!centralStatus?.configured || centralSyncBusy}
                                aria-disabled={!centralStatus?.configured || centralSyncBusy}
                              >
                                {centralSyncBusy ? LABELS.SYNCING : LABELS.SYNC_RUN}
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
                                          title={formatOptionalText((item.metrics as any)?.last_error)}
                                        >
                                          {item.lastDisconnect !== '--' ? item.lastDisconnect : item.lastError}
                                        </span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">최근 복구</span>
                                        <span className="settings-comm-summary-value">
                                          {item.lastRecoveryAt !== '--' ? item.lastRecoveryAt : item.lastOk}
                                        </span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">복구 시간</span>
                                        <span className="settings-comm-summary-value">{item.recovery}</span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">복구 횟수</span>
                                        <span className="settings-comm-summary-value">{item.recoveryCount}</span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">현재 다운타임</span>
                                        <span className="settings-comm-summary-value">{item.currentDowntime}</span>
                                      </div>
                                      <div className="settings-comm-summary-row">
                                        <span className="settings-comm-summary-label">누적 다운타임</span>
                                        <span className="settings-comm-summary-value">{item.totalDowntime}</span>
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
                                      <span className="settings-comm-label">복구 횟수</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.recovery_count)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">현재 다운타임</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.current_downtime_sec ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">누적 다운타임</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.total_downtime_sec ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 끊김</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_disconnect_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 복구</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_recovery_at ?? null)}
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
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">복구 횟수</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalNumber(metrics?.recovery_count)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">현재 다운타임</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.current_downtime_sec ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">누적 다운타임</span>
                                      <span className="settings-comm-value">
                                        {formatOptionalSeconds(metrics?.total_downtime_sec ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 끊김</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_disconnect_time ?? null)}
                                      </span>
                                    </div>
                                    <div className="settings-comm-row">
                                      <span className="settings-comm-label">최근 복구</span>
                                      <span className="settings-comm-value">
                                        {formatTimeFromSec(metrics?.last_recovery_at ?? null)}
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
                          <div className="settings-comm-empty">{MESSAGES.WAITING_COMM_METRICS}</div>
                        )}
                      </div>
                    </div>

    <div
      className="settings-section"
      id="settings-observability"
      ref={registerSettingsSection('settings-observability')}
    >
      <div className="settings-section-title">{LABELS.OPER_OBSERVABILITY}</div>
      <div className="settings-test-grid settings-observability-grid">
        <div className="settings-test-item">
          <div className="settings-test-header">
            <span className="settings-test-title">지표 내보내기</span>
            <span className={`settings-test-badge ${lastExportPath ? 'ok' : 'warn'}`}>
              {lastExportPath ? LABELS.READY : LABELS.NONE}
            </span>
          </div>
          <div className="settings-comm-log">
            <div className="settings-comm-log-actions">
              <button
                type="button"
                className="settings-comm-log-button"
                onClick={handleExportObservability}
                disabled={exportBusy}
                aria-disabled={exportBusy}
              >
                {exportBusy ? LABELS.EXPORTING : LABELS.EXPORT}
              </button>
              <button
                type="button"
                className="settings-comm-log-button"
                onClick={handleCopyObservabilityExportPath}
                disabled={!lastExportPath}
                aria-disabled={!lastExportPath}
              >
                {LABELS.COPY_PATH}
              </button>
              <button
                type="button"
                className="settings-comm-log-button"
                onClick={handleOpenObservabilityExportFolder}
                disabled={!lastExportPath}
                aria-disabled={!lastExportPath}
              >
                {LABELS.OPEN_FOLDER}
              </button>
              <button
                type="button"
                className="settings-comm-log-button"
                onClick={handleOpenObservabilityExportFile}
                disabled={!lastExportPath}
                aria-disabled={!lastExportPath}
              >
                {LABELS.OPEN_FILE}
              </button>
            </div>
            <span className="settings-comm-log-value">{lastExportPath ?? '--'}</span>
          </div>
        </div>
        <div className="settings-test-item">
          <div className="settings-test-header">
            <span className="settings-test-title">윈도 지표</span>
            <span className={`settings-test-badge ${hasWindowIssue ? 'error' : 'ok'}`}>
              {hasWindowIssue ? LABELS.WARNING : LABELS.NORMAL}
            </span>
          </div>
          <div className="settings-test-meta">
            <span>윈도: {statsWindow?.window_sec ?? '--'}s</span>
            <span>
              요청: {statsWindow?.request_count ?? '--'} / 에러: {statsWindow?.error_count ?? '--'}
            </span>
            <span>
              에러율: {windowErrorRate === null ? '--' : `${Math.round(windowErrorRate * 100)}%`}
            </span>
            <span>P95: {windowP95Text}</span>
            <span>RPS: {statsWindow?.requests_per_sec ?? '--'}</span>
          </div>
          {statsWindow?.top_paths?.length ? (
            <div className="settings-test-message">
              Top: {statsWindow.top_paths.map((item) => item.path).join(', ')}
            </div>
          ) : (
            <div className="settings-test-message">Top: --</div>
          )}
        </div>
        <div className="settings-test-item">
          <div className="settings-test-header">
            <span className="settings-test-title">에러 큐</span>
            <span className={`settings-test-badge ${errorQueueSize ? 'error' : 'ok'}`}>
              {errorQueueSize ? LABELS.OCCURRED : LABELS.NORMAL}
            </span>
          </div>
          <div className="settings-test-meta">
            <span>대기: {errorQueueText}</span>
            <span>최근: {formatTimeFromSec(lastErrorAt)}</span>
            <span>소스: {stats?.errors?.last_error_source ?? '--'}</span>
          </div>
          <div className="settings-test-message">
            메시지: {stats?.errors?.last_error_message ?? '--'}
          </div>
          <div className="settings-observability-actions">
            <button
              type="button"
              className="settings-test-button"
              onClick={() => loadObservabilityErrors()}
              disabled={observabilityLoading}
              aria-disabled={observabilityLoading}
            >
              {observabilityLoading ? '불러오는 중...' : '새로고침'}
            </button>
            <button
              type="button"
              className="settings-test-button"
              onClick={handleClearObservabilityErrors}
              disabled={!errorQueueSize}
              aria-disabled={!errorQueueSize}
            >
              {LABELS.CLEAR}
            </button>
          </div>
        </div>
      </div>
      <div className="settings-observability-errors">
        <div className="settings-comm-log-header">
          <span className="settings-comm-log-label">에러 큐 상세</span>
          <span className="settings-observability-count">
            {observabilityErrors?.summary?.queue_size ?? 0}{LABELS.UNIT_CASES}
          </span>
        </div>
        {observabilityLoading ? (
          <div className="settings-error-empty">불러오는 중...</div>
        ) : observabilityErrors?.items?.length ? (
          <div className="settings-error-list">
            {observabilityErrors.items.map((item, index) => (
              <div key={`${item.source}-${item.time}-${index}`} className="settings-error-item">
                <div className="settings-error-head">
                  <span className="settings-error-source">{item.source}</span>
                  <span className="settings-error-time">
                    {item.time_iso ?? new Date(item.time * 1000).toLocaleString()}
                  </span>
                  {item.repeat && item.repeat > 1 && (
                    <span className="settings-error-repeat">x{item.repeat}</span>
                  )}
                </div>
                <div className="settings-error-message">{item.message}</div>
                {item.detail && <div className="settings-error-detail">{item.detail}</div>}
                {item.path && <div className="settings-error-detail">{item.path}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="settings-error-empty">{LABELS.NO_ERROR}</div>
        )}
      </div>
      <div className="settings-observability-errors">
        <div className="settings-comm-log-header">
          <span className="settings-comm-log-label">브라우저 오류</span>
          <div className="settings-comm-log-actions">
            <button
              type="button"
              className="settings-comm-log-button"
              onClick={clearFrontErrors}
              disabled={frontErrors.length === 0}
              aria-disabled={frontErrors.length === 0}
            >
              {LABELS.CLEAR}
            </button>
          </div>
        </div>
        {frontErrors.length ? (
          <div className="settings-error-list">
            {frontErrors.slice(0, 5).map((item, index) => (
              <div key={`${item.type}-${item.time}-${index}`} className="settings-error-item">
                <div className="settings-error-head">
                  <span className="settings-error-source">{item.type}</span>
                  <span className="settings-error-time">{formatTime(item.time)}</span>
                </div>
                <div className="settings-error-message">{item.message}</div>
                {item.detail && <div className="settings-error-detail">{item.detail}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="settings-error-empty">{LABELS.NO_BROWSER_ERROR}</div>
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
                return <span className="settings-spot-badge ok">{LABELS.NORMAL}</span>;
              }
              if (status.type === 'loading') {
                return <span className="settings-spot-badge warn">{LABELS.CONNECTING}</span>;
              }
              if (status.type === 'warn') {
                return <span className="settings-spot-badge warn">{LABELS.DELAYED}</span>;
              }
              return <span className="settings-spot-badge error">{STATUS.ERROR}</span>;
            })()}
          </div>
          <div className="settings-spot-meta">
            <span>{LABELS.LAST_RECEIVE}: {spotLastSuccessAt ? new Date(spotLastSuccessAt).toLocaleTimeString() : LABELS.NOT_RECEIVED}</span>
            <span>URL: {spotConfig?.image_url ?? (settingsForm.spotIp ? `http://${settingsForm.spotIp}/image.jpg` : '-')}</span>
          </div>
        </div>
        <div className="settings-spot-frame">
          {spotImageUrl ? (
            <img src={spotImageUrl} alt="SPOT preview" />
          ) : (
            <div className="settings-spot-empty">{LABELS.NO_PREVIEW}</div>
          )}
          {spotImageLoading && (
            <div className="settings-spot-overlay">{LABELS.LOADING_IMAGE}</div>
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
                          <span className="settings-toggle-label">{LABELS.AUTO_SAVE_USE}</span>
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
                                  {pathCheckBusy ? LABELS.CHECKING : LABELS.CHECK}
                                </button>
                                {result?.status === 'WARN' && (
                                  <button
                                    type="button"
                                    className="settings-path-button secondary"
                                    onClick={() => createPath(pathValue)}
                                  >
                                    {LABELS.CREATE_FOLDER}
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
                          className={`settings-field settings-toggle-field ${isSettingsFieldDirty('thresholdMasterOn') ? 'changed' : ''}`}
                        >
                          <span className="settings-toggle-label">전체 알림 사용</span>
                          <button
                            type="button"
                            className="settings-toggle"
                            aria-pressed={settingsForm.thresholdMasterOn}
                            onClick={() => handleMasterToggle(!settingsForm.thresholdMasterOn)}
                          >
                            <span className="settings-toggle-text">{settingsForm.thresholdMasterOn ? 'ON' : 'OFF'}</span>
                          </button>
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
                      <div className="settings-section-title">
                        <span>보안</span>
                        <span className={`settings-test-badge ${settingsForm.passwordSet ? 'ok' : 'warn'}`}>
                          {settingsForm.passwordSet ? '설정됨' : '미설정'}
                        </span>
                      </div>
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
                  onClick={() => handleRestoreBackup()}
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
                  onClick={() => handleSaveSettings()}
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
            </>
            )}
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
            timeSeriesFrames,
            onSpotImageLoaded: handleSpotImageLoaded,
            onSpotImageError: handleSpotImageError,
            requestFocus,
            seriesWindowMin,
            seriesPaused,
            showThresholds,
            setSeriesWindowMin,
            setSeriesPaused,
            setShowThresholds,
            handleSnapshot,
            snapshotLoading,
            nowTick,
            customNotice,
            setCustomNotice,
            layoutEditing,
            setLayoutEditing,
          }}
        >
        <LayoutEditContext.Provider value={{ isEditing: layoutEditing, deleteWidget: handleRemoveWidget, updateWidget: handleUpdateWidget }}>
           <scene.Component model={scene} />
        </LayoutEditContext.Provider>
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
  timeSeriesFrames: Record<string, SeriesFrame> | null;
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
  // Time Series Control
  seriesWindowMin: number;
  seriesPaused: boolean;
  showThresholds: boolean;
  setSeriesWindowMin: (min: number) => void;
  setSeriesPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setShowThresholds: (show: boolean) => void;
  handleSnapshot: () => void;
  snapshotLoading: boolean;
  nowTick: number; // For XAxis domain sync
  customNotice: string;
  setCustomNotice: (notice: string) => void;
  layoutEditing: boolean;
  setLayoutEditing: React.Dispatch<React.SetStateAction<boolean>>;
};

const DataContext = React.createContext<DataContextValue>({
  data: null,
  thresholds: buildThresholdStateFromConfig(),
  timeSeriesFrames: null,
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
  seriesWindowMin: 30,
  seriesPaused: false,
  showThresholds: true,
  setSeriesWindowMin: () => undefined,
  setSeriesPaused: () => undefined,
  setShowThresholds: () => undefined,
  handleSnapshot: () => undefined,
  snapshotLoading: false,
  nowTick: Date.now(),
  customNotice: '',
  setCustomNotice: () => undefined,
  layoutEditing: false,
  setLayoutEditing: () => undefined,
});

function KpiComponent() {
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
          <span className="kpi-value">{formatNumber(data.Speed ?? NaN, 1)}</span>
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
          <span className="kpi-value">{formatNumber(data.Press ?? NaN, 1)}</span>
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
          <span className="kpi-mini-value">{formatInteger(data.Count ?? 0)}</span>
        </div>
        <div className={`kpi-mini ${endPosThresholdHit ? 'kpi-mini-threshold' : ''}`}>
          <div className="kpi-mini-header">
            <span className="kpi-mini-label">종료 위치</span>
            {endPosThresholdHit && <span className="threshold-badge">임계</span>}
          </div>
          <div className="kpi-mini-value-row">
            <span className="kpi-mini-value">{formatNumber(data.EndPos ?? NaN, 1)}</span>
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

function SpotComponent() {
    const { data, spotAlertActive, lastDataAt, thresholds } = React.useContext(DataContext);
    const [sparklineValues, setSparklineValues] = useState<number[]>([]);
    const spotValue = useLastValidNumber(data?.Spot);
    
    const missing = !Number.isFinite(data?.Spot);
    const spotDisplayValue = Number.isFinite(spotValue ?? NaN) ? spotValue! : (data?.Spot ?? NaN);
  const computed = data?.Computed;
  const spotState = mapSpotLevel(computed?.spot_level) ?? getSpotState(spotDisplayValue, spotAlertActive);
  const spotThresholdHit = computed?.thresholds?.spot ?? isThresholdHit(thresholds, 'spot', spotValue);
  const spotConfigThreshold = getThresholdValue(thresholds, 'spot');
    const spotPercent = calcPercent(spotDisplayValue, SPOT_MAX_TEMP);
    const sparklineThresholds = useMemo(() => {
      const list = [SPOT_NORMAL_MIN, SPOT_HIGH_MIN, SPOT_WARN_TEMP];
      if (typeof spotConfigThreshold === 'number' && Number.isFinite(spotConfigThreshold)) {
        const exists = list.some((value) => Math.abs(value - spotConfigThreshold) < 0.01);
        if (!exists) {
          list.push(spotConfigThreshold);
        }
      }
      return list;
    }, [spotConfigThreshold]);
    const { linePath, areaPath, points, thresholdLines } = useMemo(
      () =>
        buildSparklinePaths(
          sparklineValues,
          100,
          60,
          sparklineThresholds,
          { min: SPOT_NORMAL_MIN, max: SPOT_WARN_TEMP }
        ),
      [sparklineValues, sparklineThresholds]
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
                className={[
                  'sparkline-threshold',
                  line.value === SPOT_WARN_TEMP
                    ? 'sparkline-threshold-warn'
                    : line.value === SPOT_HIGH_MIN
                      ? 'sparkline-threshold-high'
                      : line.value === SPOT_NORMAL_MIN
                        ? 'sparkline-threshold-normal'
                        : '',
                  typeof spotConfigThreshold === 'number' &&
                  Number.isFinite(spotConfigThreshold) &&
                  Math.abs(line.value - spotConfigThreshold) < 0.01
                    ? 'sparkline-threshold-config'
                    : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
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

function TempsComponent() {
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
              <span className="temp-label">{LABELS.CONTAINER_FRONT}</span>
              {tempFThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Temp_F ?? NaN, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${tempBClass}`}>
            <div className="temp-header">
              <span className="temp-label">{LABELS.CONTAINER_BACK}</span>
              {tempBThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Temp_B ?? NaN, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${billetTempClass}`}>
            <div className="temp-header">
              <span className="temp-label">{LABELS.BILLET_TEMP}</span>
              {billetTempThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Billet_Temp ?? NaN, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${billetLengthClass}`}>
            <div className="temp-header">
              <span className="temp-label">{LABELS.BILLET_LEN}</span>
              {billetLengthThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
            </div>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Billet_Length ?? NaN, 1)}</span>
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

function MoldsComponent() {
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
  const mold1 = mapMoldLevel(moldLevels?.Mold1) ?? getMoldState(data.Mold1 ?? 0).className;
  const mold2 = mapMoldLevel(moldLevels?.Mold2) ?? getMoldState(data.Mold2 ?? 0).className;
  const mold3 = mapMoldLevel(moldLevels?.Mold3) ?? getMoldState(data.Mold3 ?? 0).className;
  const mold4 = mapMoldLevel(moldLevels?.Mold4) ?? getMoldState(data.Mold4 ?? 0).className;
  const mold5 = mapMoldLevel(moldLevels?.Mold5) ?? getMoldState(data.Mold5 ?? 0).className;
  const mold6 = mapMoldLevel(moldLevels?.Mold6) ?? getMoldState(data.Mold6 ?? 0).className;
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="mold-grid">
            <div className={`mold-tile ${mold1}`}>
            <span className="mold-label">Mold 1</span>
            <span className="mold-value">{formatNumber(data.Mold1 ?? NaN, 1)}</span>
          </div>
            <div className={`mold-tile ${mold2}`}>
            <span className="mold-label">Mold 2</span>
            <span className="mold-value">{formatNumber(data.Mold2 ?? NaN, 1)}</span>
          </div>
            <div className={`mold-tile ${mold3}`}>
            <span className="mold-label">Mold 3</span>
            <span className="mold-value">{formatNumber(data.Mold3 ?? NaN, 1)}</span>
          </div>
            <div className={`mold-tile ${mold4}`}>
            <span className="mold-label">Mold 4</span>
            <span className="mold-value">{formatNumber(data.Mold4 ?? NaN, 1)}</span>
          </div>
            <div className={`mold-tile ${mold5}`}>
            <span className="mold-label">Mold 5</span>
            <span className="mold-value">{formatNumber(data.Mold5 ?? NaN, 1)}</span>
          </div>
            <div className={`mold-tile ${mold6}`}>
            <span className="mold-label">Mold 6</span>
            <span className="mold-value">{formatNumber(data.Mold6 ?? NaN, 1)}</span>
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

function EnvComponent() {
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
              <span className="env-label">{LABELS.ENV_TEMP}</span>
              {tempThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
            </div>
            <div className="env-value-row">
              <span className="env-value">{formatNumber(tempDisplay ?? NaN, 1)}</span>
              <span className="env-unit">{SPOT_UNIT}</span>
            </div>
            <span className={`env-badge ${tempState.className}`}>{tempState.label}</span>
          </div>
          <div className={`env-tile ${humidityThresholdHit ? 'env-threshold' : ''}`}>
            <div className="env-header">
              <span className="env-label">{LABELS.ENV_HUMID}</span>
              {humidityThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
            </div>
            <div className="env-value-row">
              <span className="env-value">{formatNumber(humidityDisplay ?? NaN, 1)}</span>
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


function CameraComponent() {
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
              alt={LABELS.SPOT_CAMERA}
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
           <button onClick={() => requestFocus(1)}>&lt;-Focus</button>
           <button onClick={() => requestFocus(-1)}>Focus-&gt;</button>
        </div>
      </div>
    );
};

function TimeSeriesWidget() {
    const { 
      timeSeriesFrames, 
      seriesWindowMin, 
      setSeriesWindowMin, 
      seriesPaused, 
      setSeriesPaused, 
      showThresholds, 
      setShowThresholds,
      handleSnapshot,
      snapshotLoading,
      nowTick
    } = React.useContext(DataContext);
    
    // Convert frames to Recharts data
    // Optimizing: Only rebuild when frames update
    // Use a ref to store the last valid data for freezing
    const lastChartDataRef = useRef<any[]>([]);

    const chartData = useMemo(() => {
      // If paused, return the last known data to "freeze" the chart
      if (seriesPaused && lastChartDataRef.current.length > 0) {
        return lastChartDataRef.current;
      }

      if (!timeSeriesFrames) return [];
      
      // Use 'process' frame as master for time, as it contains Speed/Press (always present)
      const master = timeSeriesFrames['process']; 
      if (!master) return [];

      const times = master.fields[0].values; // Time column
      const length = master.length;
      
      const data = [];
      for (let i = 0; i < length; i++) {
         const time = times[i];
         const item: any = { time };
         
         // Iterate all groups (frames)
         Object.values(timeSeriesFrames).forEach((frame) => {
            // Check length alignment
            if (i >= frame.length) return;
            
            // Iterate all fields in the frame (skip time at index 0)
            for (let j = 1; j < frame.fields.length; j++) {
                const field = frame.fields[j];
                item[field.name] = field.values[i];
            }
         });
         data.push(item);
      }
      
      lastChartDataRef.current = data;
      return data;
    }, [timeSeriesFrames, seriesPaused]);
    
    if (!timeSeriesFrames) return <div style={{color: 'white', padding: '16px'}}>Loading data...</div>;

    return (
      <div className="card timeseries-card" style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
         {/* Controls Header within the Widget */}
         <div className="timeseries-controls" style={{ 
            display: 'flex', 
            justifyContent: 'flex-end', 
            alignItems: 'center', 
            gap: '8px', 
            padding: '4px 8px', 
            borderBottom: '1px solid var(--border-muted)',
            background: 'var(--bg-header)'
         }}>
             <div className="series-group">
                {[1, 5, 10, 30, 60].map((min) => (
                  <button
                    key={min}
                    className={`status-action ${seriesWindowMin === min ? 'active' : ''}`}
                    style={{ minWidth: '32px', padding: '0 4px', opacity: seriesWindowMin === min ? 1 : 0.5, fontSize: '11px', height: '24px' }}
                    onClick={() => setSeriesWindowMin(min)}
                  >
                    {min}m
                  </button>
                ))}
            </div>
            <div style={{width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px'}}></div>
            <button
                className={`status-action ${seriesPaused ? 'warn' : ''}`}
                onClick={() => setSeriesPaused((prev) => !prev)}
             >
                {seriesPaused ? 'Pause' : 'Live'}
             </button>
             <label style={{ display: 'flex', alignItems: 'center', fontSize: '11px', cursor: 'pointer', gap: '4px', userSelect: 'none', color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={showThresholds}
                  onChange={(e) => setShowThresholds(e.target.checked)}
                />
                {LABELS.THRESHOLDS}
             </label>
             <div style={{width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px'}}></div>
             <button
                 className={`status-action ${snapshotLoading ? 'loading' : ''}`}
                 onClick={handleSnapshot}
                 disabled={snapshotLoading}
                 title={LABELS.SAVE_SNAPSHOT}
             >
                 {LABELS.SAVE}
             </button>
         </div>

         <div style={{ flexGrow: 1, minHeight: 0 }}>
             <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                   <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" />
                   <XAxis 
                     dataKey="time" 
                     type="number" 
                     domain={['dataMin', (min: number) => min + seriesWindowMin * 60 * 1000]} 
                     allowDataOverflow={true}
                     tickFormatter={(unixTime) => new Date(unixTime).toLocaleTimeString()}
                     stroke="var(--text-muted)"
                     height={30}
                   />
                   <YAxis stroke="var(--text-muted)" width={40} />
                   <Tooltip 
                     labelFormatter={(label) => new Date(label).toLocaleTimeString()}
                     contentStyle={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-main)', color: 'var(--text-primary)' }}
                   />
                   <Legend verticalAlign="top" height={36}/>
                   
                   {/* Defined Lines - Primary Process */}
                   <Line type="monotone" dataKey="Speed" stroke="var(--color-speed)" dot={false} strokeWidth={2} name="속도" isAnimationActive={false} />
                   <Line type="monotone" dataKey="Press" stroke="var(--color-press)" dot={false} strokeWidth={2} name="압력" isAnimationActive={false} />
                   <Line type="monotone" dataKey="Spot" stroke="var(--color-spot)" dot={false} strokeWidth={2} name="SPOT" isAnimationActive={false} />
                   <Line type="monotone" dataKey="Temp_F" stroke="var(--color-temp-f)" dot={false} strokeWidth={1} name="온도(F)" isAnimationActive={false} />
                   <Line type="monotone" dataKey="Temp_B" stroke="var(--color-temp-b)" dot={false} strokeWidth={1} name="온도(B)" isAnimationActive={false} />
                   
                   {/* Additional Process Data */}
                   <Line type="monotone" dataKey="Billet_Length" stroke="var(--color-billet-len)" dot={false} strokeWidth={1} name="빌렛 길이" isAnimationActive={false} />
                   <Line type="monotone" dataKey="Count" stroke="var(--color-count)" dot={false} strokeWidth={1} name="생산 수량" isAnimationActive={false} />
                   <Line type="monotone" dataKey="EndPos" stroke="var(--color-endpos)" dot={false} strokeWidth={1} name="종료 위치" isAnimationActive={false} />



                   {/* Other Temperatures & Environment */}
                   <Line type="monotone" dataKey="Billet_Temp" stroke="var(--color-billet-temp)" dot={false} strokeWidth={1} name="빌렛 온도" isAnimationActive={false} />
                   <Line type="monotone" dataKey="At_Temp" stroke="var(--color-env-temp)" dot={false} strokeWidth={1} name="환경 온도" isAnimationActive={false} />
                   <Line type="monotone" dataKey="At_Pre" stroke="var(--color-env-pre)" dot={false} strokeWidth={1} name="환경 습도" isAnimationActive={false} />
                   
                   {showThresholds && (
                      <>
                        <ReferenceLine y={SPEED_MAX} label="Max Speed" stroke="var(--state-danger)" strokeDasharray="3 3" />
                         {/* Add more reference lines if needed based on thresholds context */}
                      </>
                   )}

                </LineChart>
             </ResponsiveContainer>
         </div>
      </div>
    );
};

export default App;
