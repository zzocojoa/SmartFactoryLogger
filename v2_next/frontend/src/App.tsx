import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import ReactMarkdown from 'react-markdown';
import {
  FactoryData,
  SpotConfig,
  HealthSnapshot,
  StatsSnapshot,
  ObservabilityErrorsResponse,
  PathHealthState,
  ConnectionTestState,
  ConfigSnapshot,
  SettingsFormState,
  ConfigApplyResult,
  ConfigUpdateResponse,
  ThresholdKey,
  ThresholdEntry,
  ThresholdState,
  ConnectionTargetKey,
  ThresholdItem,
  ConnectionTestResult,
  FrontendErrorEntry,
  NotificationLevel,
  NotificationItem,
  CommLogInfo,
  CentralStatus,
  CentralSyncResult,
  CommMetrics,
  CommChannelMetrics,
  CommSpotMetrics,
  ObservabilityErrorItem,
  PathHealthResult,
  LayoutSnapshot,
  LayoutSlotSummary,
  LayoutMap
} from './shared/types';
import { useSystemViewModel } from './domains/Observability/hooks/useSystemViewModel';
import { useSpotViewModel } from './domains/FacilityData/hooks/useSpotViewModel';
import { useConfigViewModel } from './domains/Configuration/hooks/useConfigViewModel';
import { useLayoutViewModel } from './domains/Configuration/hooks/useLayoutViewModel';
import { useMetricsViewModel } from './domains/FacilityData/hooks/useMetricsViewModel';
import { useViewportScale, applyRowHeightToCSS } from './domains/Configuration/hooks/useViewportScale';
import './App.css';
import packageJson from '../package.json';
const UPlotChart = React.lazy(() => import('./domains/FacilityData/components/UPlotChart').then(m => ({ default: m.UPlotChart })));
import type uPlot from 'uplot';

// --- Widget Imports ---
import { KpiComponent } from './domains/FacilityData/components/widgets/KpiWidget';
import { SpotComponent } from './domains/FacilityData/components/widgets/SpotWidget';
import { TempsComponent } from './domains/FacilityData/components/widgets/TempsWidget';
import { MoldsComponent } from './domains/FacilityData/components/widgets/MoldsWidget';
import { EnvComponent } from './domains/FacilityData/components/widgets/EnvWidget';
import { CameraComponent } from './domains/FacilityData/components/widgets/CameraWidget';
import { TimeSeriesWidget } from './domains/FacilityData/components/widgets/TimeSeriesWidget';

// UPlot Series Colors Mapping - Moved to seriesCatalog.ts
import { SERIES_COLORS } from './domains/FacilityData/timeseries/seriesCatalog';

/* Recharts imports removed */
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { getDashboardScene, WidgetType, WidgetRegistry, DashboardItem, DASHBOARD_LAYOUT_KEYS } from './scenes/DashboardScene';
import { SceneDataNode, SceneGridItemLike, SceneGridLayout, SceneGridItem, SceneObjectBase } from '@grafana/scenes';
import { ReactWidget } from './scenes/ReactWidgetObject';
import { buildSeriesSample } from './domains/FacilityData/timeseries/seriesSampling';
import { SeriesBuffer } from './domains/FacilityData/timeseries/seriesBuffer';
import { buildGroupedFrames, buildTimeSeriesFrame, SeriesFrame } from './domains/FacilityData/timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from './domains/FacilityData/timeseries/seriesCatalog';
import { buildPanelData } from './domains/FacilityData/timeseries/seriesPanelData';
import { buildSeriesThresholds } from './domains/FacilityData/timeseries/seriesThresholds';
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
} from './shared/constants/uiText';
import * as LOGIC from './shared/constants/logic';
import * as THEME from './shared/constants/theme';
import { useModal } from './shared/hooks/useGlobalModalContext';
import { useTheme } from './shared/hooks/useThemeContext';
const AIChatbot = React.lazy(() => import('./AI/components/AIChatbot').then(m => ({ default: m.AIChatbot })));

const MAX_NOTIFICATIONS = 50;

import { LayoutEditContext } from './domains/Configuration/context/LayoutEditContext';

// Initialize Scenes Runtime (guarded for HMR)
if (typeof window !== 'undefined') {
  if (!(window as any).__SCENES_INIT__) {
    initScenesRuntime();
    (window as any).__SCENES_INIT__ = true;
  }
} else {
  initScenesRuntime();
}

import { apiClient, API_BASE } from './shared/api/client';
import { configService } from './domains/Configuration/api/configService';
// Data Contexts
import { FactoryDataContext } from './domains/FacilityData/context/FactoryDataContext';
import { SpotContext } from './domains/FacilityData/context/SpotContext';
import { UIContext } from './domains/FacilityData/context/UIContext';
import { SnapshotContext } from './domains/FacilityData/context/SnapshotContext';

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

const MarkdownWidget = ({ item, model }: { item: DashboardItem; model: ReactWidget }) => {
  const { updateWidget } = React.useContext(LayoutEditContext);
  const { isContentEditing: editing } = model.useState();
  const [editValue, setEditValue] = useState(item.properties?.content || '');

  useEffect(() => {
    setEditValue(item.properties?.content || '');
  }, [item.properties?.content]);

  const handleSave = () => {
    updateWidget(item.key, { properties: { ...item.properties, content: editValue } });
    model.setState({ isContentEditing: false });
  };

  return (
    <div className="scene-react-widget card" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
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
        <div className="notice-content markdown-body" style={{ flex: 1, overflow: 'auto' }}>
          <ReactMarkdown>{item.properties?.content || ''}</ReactMarkdown>
        </div>
      )}
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





import { buildLayoutMap } from './shared/utils/layoutUtils';
import {
  calcRecoverySec,
  formatAgeSec,
  formatInteger,
  formatMetaTime,
  formatNumber,
  formatOptionalNumber,
  formatOptionalSeconds,
  formatOptionalText,
  formatTime,
  formatTimeFromSec,
} from './shared/utils/formatters';
import { isValidIp, isValidNumberInput, isValidPort, parseThresholdValue } from './shared/utils/validators';
import {
  getEnvHumidityState,
  getEnvTempState,
  getMoldState,
  getPressState,
  getSpeedState,
  getSpotState,
  mapEnvPreLevel,
  mapEnvTempLevel,
  mapMoldLevel,
  mapPressLevel,
  mapSpeedLevel,
  mapSpotLevel,
} from './shared/utils/stateMappers';

// --- Extracted Utilities (Phase 9 Step 1) ---
import { clampNumber, buildSparklinePaths, calcPercent } from './shared/utils/sparkline';
import {
  buildThresholdStateFromConfig,
  buildThresholdStateFromForm,
  isThresholdHit,
  getThresholdValue,
  THRESHOLD_LABELS,
} from './shared/utils/thresholds';
import type { ThresholdLevel } from './shared/utils/thresholds';
import { buildCommBadge, buildSpotCommBadge, getCameraStatus } from './shared/utils/commBadge';
import type { CommBadge } from './shared/utils/commBadge';
import { useThresholdLevel } from './shared/hooks/useThresholdLevel';
import { useSustainedFlag } from './shared/hooks/useSustainedFlag';
import { useLastValidNumber } from './shared/hooks/useLastValidNumber';
import { useNotifications } from './shared/hooks/useNotifications';
import { useSnapshotManager } from './shared/hooks/useSnapshotManager';
import { useObservabilityHandlers } from './shared/hooks/useObservabilityHandlers';
import { useSettingsFormHandlers } from './shared/hooks/useSettingsFormHandlers';
import { useLayoutHandlers } from './shared/hooks/useLayoutHandlers';

function App() {
  const { mode, activeCycle, setMode } = useTheme();
  const modal = useModal();

  // Viewport scale for responsive grid
  const { rowHeight, scaleFactor, aspectRatio } = useViewportScale();
  
  // Apply row height to CSS variable when it changes
  useEffect(() => {
    applyRowHeightToCSS(rowHeight);
  }, [rowHeight]);

  // Time Series States (UI Control - stays in App)
  const [seriesWindowMin, setSeriesWindowMinState] = useState(() => {
    try {
      const saved = localStorage.getItem('seriesWindowMin');
      return saved ? parseInt(saved, 10) : 30;
    } catch { return 30; }
  });
  const setSeriesWindowMin = useCallback((min: number) => {
    setSeriesWindowMinState(min);
    try { localStorage.setItem('seriesWindowMin', String(min)); } catch {}
  }, []);
  const [seriesPaused, setSeriesPaused] = useState(false);
  const [showThresholds, setShowThresholds] = useState(true);

  // timeSeriesDataNode stays in App for minimal change approach
  const timeSeriesDataNode = useMemo(() => new SceneDataNode(), []);

  const {
    health,
    stats,
    observabilityErrors,
    observabilityLoading,
    pathHealth,
    reconnectBusy,
    pathCheckBusy,
    lastExportPath,
    commLogInfo,
    fetchHealth,
    fetchStats,
    loadObservabilityErrors,
    clearObservabilityErrors,
    reconnect,
    runConnectionTest,
    checkPathHealth,
    checkPathsHealth,
    createPath,
    browseFolder,
    setPathHealth,
    setPathCheckBusy,
    fetchLatestExportPath,
    exportObservability,
    openExportFolder,
    openExportFile,
    fetchCommLogInfo,
    openCommLogPath,
    openCommLogFile,
    saveSnapshot,
    connectionTest
  } = useSystemViewModel();
  
  useEffect(() => {
    fetchCommLogInfo();
  }, [fetchCommLogInfo]);

  const {
    config: spotConfig,
    imageUrl: spotImageUrl,
    imageError: spotImageError,
    imageLoading: spotImageLoading,
    lastSuccessAt: spotLastSuccessAt,
    focusBusy,
    refreshConfig: fetchSpotConfig,
    handleImageLoad: handleSpotImageLoaded,
    handleImageError: handleSpotImageError,
    controlFocus: requestFocus
  } = useSpotViewModel();

  const {
    settingsOpen,
    settingsLoading,
    settingsError,
    settingsInfo,
    settingsForm,
    settingsBaseline,
    settingsRestartRequired,
    settingsApplyResult,
    settingsPending,
    settingsPendingBusy,
    settingsConfigPath,
    configWritable,
    overrideEnabled,
    overrideMeta,
    centralStatus,
    centralSyncBusy,
    thresholdConfig,
    settingsToast,
    hasSettingsChanges,
    validationErrors,
    hasValidationError,
    activeThresholds: thresholdState,

    setSettingsOpen,
    loadSettings,
    updateSettingsField,
    handleSaveSettings,
    handleRestoreDefaults,
    handleRestoreBackup,
    handlePendingApply,
    handlePendingClear,
    handleMasterToggle,
    handleOverrideToggle,
    handleExternalRefresh,
    handleExternalIgnore,
    handleCentralSync,
    showSettingsToast,
    setSettingsError,
    setSettingsInfo,
    fetchCentralStatus,
    isSettingsFieldDirty,
    externalConfigPending,
    externalConfigPendingAt,
    overrideBusy
  } = useConfigViewModel();

  const {
    layoutSnapshot,
    layoutSlots,
    layoutActiveId,
    layoutEditing,
    layoutLoadError,
    layoutSaveMessage,
    layoutSaveError,
    storageMode,
    setLayoutEditing,
    setStorageMode,
    loadLayoutSnapshot,
    handleSaveLayout,
    handleRestoreLayout,
    handleDeleteLayout,
    applyPreset,
    updateWidget,
    deleteWidget,
    addWidget,
    fetchLayoutSlots
  } = useLayoutViewModel();

  const {
    data,
    connected,
    lastDataAt,
    latencyMs,
    timeSeriesFrames,
    timeSeriesAllFrame,
    getSeriesSamples
  } = useMetricsViewModel({
    seriesPaused,
    seriesWindowMin,
    showThresholds,
    thresholdConfig
  });

  const [frontErrors, setFrontErrors] = useState<FrontendErrorEntry[]>([]);
  const [layoutRestoreError, setLayoutRestoreError] = useState<string | null>(null);
  const [layoutRestoreMessage, setLayoutRestoreMessage] = useState<string | null>(null);
  /* centralSyncBusy moved to useConfigViewModel */

  const [nowTick, setNowTick] = useState(() => Date.now());

  // Settings State moved to useConfigViewModel
  /*
  const [settingsOpen, setSettingsOpen] = useState(false);
  ...
  */

  // Time Series States
  // Moved thresholdConfig to hook. But we need it for buildSeriesThresholds
  const timeSeriesThresholds = useMemo(() =>
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
    , [thresholdConfig, showThresholds]);

  /*
  const [settingsRestartRequired, setSettingsRestartRequired] = useState(false);
  ...
  */

  const [menuOpen, setMenuOpen] = useState(false);
  const [widgetAddOpen, setWidgetAddOpen] = useState(false);
  const [presetOpen, setPresetOpen] = useState(false);
  
  // Password UI states
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  
  // Spot State moved to useSpotViewModel
  /*
  const [spotConfig, setSpotConfig] = useState<SpotConfig | null>(null);
  const [spotImageUrl, setSpotImageUrl] = useState('');
  const [spotImageError, setSpotImageError] = useState<string | null>(null);
  const [spotImageLoading, setSpotImageLoading] = useState(false);
  const [spotLastSuccessAt, setSpotLastSuccessAt] = useState<number | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);
  */
  /* Layout state moved to useLayoutViewModel */

  // const spotHasImage = useRef(false);
  const settingsToastTimerRef = useRef<number | null>(null);
  const settingsFingerprintRef = useRef<string | null>(null);
  const settingsExternalNotifyRef = useRef<string | null>(null);
  const statusRef = useRef<string | null>(null);
  const spotAlertRef = useRef(false);
  const cameraStatusRef = useRef<string | null>(null);
  const cameraStatusTimerRef = useRef<NodeJS.Timeout | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isManualScrollingRef = useRef(false);
  const manualScrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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



  const settingsSections = useMemo(
    () => [
      { id: 'settings-summary', label: LABELS.SUMMARY },
      { id: 'settings-central', label: LABELS.CENTRAL_CONFIG },
      { id: 'settings-comm', label: LABELS.COMM_CONFIG },
      { id: 'settings-observability', label: LABELS.OPER_OBSERVABILITY },
      { id: 'settings-spot', label: LABELS.SPOT_CAMERA },
      { id: 'settings-storage', label: LABELS.STORAGE_CONFIG },
      { id: 'settings-logging', label: LABELS.LOG_ROTATION },
      { id: 'settings-mes', label: 'MES 설정' },
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



  // --- Data Fetching Hooks (Same as before) ---


  useEffect(() => {
    return () => {
      if (settingsToastTimerRef.current !== null) {
        window.clearTimeout(settingsToastTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!layoutEditing && !menuOpen) {
      return;
    }
    fetchLayoutSlots();
  }, [layoutEditing, menuOpen, fetchLayoutSlots]);

  /* Polling and timeSeriesFrames/timeSeriesAllFrame computation moved to useMetricsViewModel */

  useEffect(() => {
    if (!timeSeriesAllFrame) {
      return;
    }
    if (seriesPaused) {
      return;
    }
    const samples = getSeriesSamples();
    const windowMs = seriesWindowMin * 60 * 1000;
    const panelData = buildPanelData(timeSeriesAllFrame, samples, windowMs);
    timeSeriesDataNode.setState({ data: panelData });
  }, [timeSeriesAllFrame, timeSeriesDataNode, seriesPaused, seriesWindowMin, getSeriesSamples]);

  useEffect(() => {
    const tick = window.setInterval(() => setNowTick(Date.now()), 500);
    return () => window.clearInterval(tick);
  }, []);


  // --- 1. Notification Management ---
  const {
    notifications,
    notificationsOpen,
    unreadCount,
    setNotificationsOpen,
    pushNotification,
    clearNotifications,
    setUnreadCount,
  } = useNotifications();

  // --- 2. Snapshot Management ---
  const { snapshotLoading, handleSnapshot } = useSnapshotManager({
    pushNotification,
    saveSnapshot,
  });

  // --- 3. Observability Handlers ---
  const {
    diagnosisBusy,
    exportBusy,
    handleDiagnosis,
    handleExportObservability,
    handleOpenObservabilityExportFile,
    handleOpenObservabilityExportFolder,
    handleCopyObservabilityExportPath,
    handleClearObservabilityErrors,
  } = useObservabilityHandlers({
    fetchHealth,
    fetchStats,
    exportObservability,
    clearObservabilityErrors,
    openExportFile,
    openExportFolder,
    lastExportPath,
    modal,
    pushNotification,
  });

  // --- 4. Settings Form & UI Handlers ---
  const {
    activeSettingsSection,
    setActiveSettingsSection,
    settingsScrollRef,
    registerSettingsSection,
    scrollToSettingsSection,
    runPathHealthCheck,
    handleConnectionTest,
    handleCreatePath,
    connectionTestBusy,
  } = useSettingsFormHandlers({
    settingsForm,
    settingsBaseline,
    settingsOpen,
    settingsReady: true, // Assuming true if settingsOpen is managed
    validationErrors,
    isSettingsFieldDirty,
    updateSettingsField,
    runConnectionTest,
    checkPathsHealth: checkPathsHealth as any,
    createPath,
    modal,
    setSettingsError,
    setPathHealth,
    pathHealth,
  });

  const handleCopyCommLogPath = useCallback(() => {
    if (!commLogInfo.path) return;
    navigator.clipboard.writeText(commLogInfo.path);
    pushNotification('경로 복사', '통신 로그 경로가 클립보드에 복사되었습니다.', 'info');
  }, [commLogInfo.path, pushNotification]);

  // --- 5. Layout Handlers ---
  const {
    layoutRef,
    saveLayout,
    restoreLayout,
    handleAddWidget,
    deleteLayoutSlot,
    handleRemoveWidget,
    handleUpdateWidget,
  } = useLayoutHandlers({
    layoutEditing,
    layoutSlots,
    layoutActiveId,
    handleSaveLayout,
    handleRestoreLayout,
    handleDeleteLayout,
    addWidget,
    deleteWidget,
    updateWidget,
    modal,
    pushNotification,
    setMenuOpen,
    setLayoutRestoreError,
    setLayoutRestoreMessage,
  });

  const handleReconnect = async () => {
    // Busy check is handled in hook, but UI disabling is via reconnectBusy from hook
    const success = await reconnect();
    if (success) {
      await modal.alert('Reconnect requested. Check status badge.');
    } else {
      await modal.alert('Reconnect failed.');
    }
  };

  const handleOpenSettings = useCallback(async () => {
    try {
      // Check if password is required
      const checkResult = await configService.verifyPassword('');
      if (checkResult.ok) {
        // No password set, open directly
        setSettingsOpen(true);
        setMenuOpen(false);
        return;
      }
    } catch (err: any) {
      if (err?.response?.status !== 403) {
        // Non-password error, open anyway
        setSettingsOpen(true);
        setMenuOpen(false);
        return;
      }
    }
    
    // Password is required, prompt user
    const password = await modal.prompt(
      '설정 화면에 접근하려면 관리자 비밀번호를 입력하세요.',
      '',
      { inputType: 'password', title: '관리자 인증' }
    );
    
    if (password === null) {
      // User cancelled
      return;
    }
    
    try {
      const result = await configService.verifyPassword(password);
      if (result.ok) {
        setSettingsOpen(true);
        setMenuOpen(false);
      }
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || '비밀번호 확인에 실패했습니다.';
      await modal.alert(errMsg);
    }
  }, [modal]);



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
      intervalSec: values.system?.interval_sec?.toString() ?? '0.2',
      statusWarnMs: values.system?.status_warn_ms?.toString() ?? '10000',
      statusOfflineMs: values.system?.status_offline_ms?.toString() ?? '20000',
      mesEnabled: values.mes?.enabled ?? false,
      mesUserId: values.mes?.userid ?? '',
      mesPassword: '', // Password is never loaded into the form for security
      mesPasswordSet: values.mes?.password_set ?? false,
      mesStartHour: String(values.mes?.starthour ?? 8),
      mesEndHour: String(values.mes?.endhour ?? 19),
      password: '',
      passwordSet: Boolean(values.settings.password_set),
    };
    return { form: nextForm, thresholds: nextThresholdState };
  }, []);

  // Config Logic moved to useConfigViewModel
  /*
  const applySettingsSnapshot = ...
  const loadSettings = ...
  const loadThresholdConfig = ...
  useEffect(() => { loadThresholdConfig() }, ...);
  useEffect(() => { if (!settingsOpen) ... }, ...);
  */

  const logPathValue = settingsForm?.logPath ?? '';
  const snapshotPathValue = settingsForm?.snapshotPath ?? '';
  const settingsReady = settingsForm !== null;
  const configReadOnly = configWritable === false;

  // validationErrors defined in hook
  // const hasValidationError = Object.keys(validationErrors).length > 0;



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
      'intervalSec',
      'statusWarnMs',
      'statusOfflineMs',
      'mesEnabled',
      'mesUserId',
      'mesPassword',
      'password',
    ];

    return keys.reduce((count, key) => {
      if (key === 'password' || key === 'mesPassword') {
        return settingsForm[key].trim() ? count + 1 : count;
      }
      if (key === 'passwordSet') { // passwordSet is not a user-editable field
        return count;
      }
      const current = settingsForm[key];
      const baseline = settingsBaseline[key];
      if (typeof current === 'boolean' || typeof baseline === 'boolean') {
        return current !== baseline ? count + 1 : count;
      }
      return String(current ?? '').trim() !== String(baseline ?? '').trim() ? count + 1 : count;
    }, 0);
  }, [settingsForm, settingsBaseline]);
  /*
  const handleExternalRefresh = ...
  const handleExternalIgnore = ...
  */


  const handleOpenCommLogPath = async () => {
    if (!commLogInfo.path) {
      return;
    }
    try {
      await openCommLogPath();
      showSettingsToast('통신 로그 폴더를 열었습니다.', 'ok');
    } catch (error) {
      console.error('Open comm log path failed', error);
      showSettingsToast('폴더 열기에 실패했습니다.', 'error');
    }
  };

  const handleOpenCommLogFile = async () => {
    if (!commLogInfo.path) {
      return;
    }
    try {
      await openCommLogFile();
      showSettingsToast('통신 로그 파일을 열었습니다.', 'ok');
    } catch (error) {
      console.error('Open comm log file failed', error);
      showSettingsToast('파일 열기에 실패했습니다.', 'error');
    }
  };

  /* Settings polling moved to useConfigViewModel */



  // --- Auto Save & Master Toggle Logic ---

  // Auto-dismiss settingsInfo
  /* Auto-dismiss settingsInfo moved to useConfigViewModel */

  /* connectionTest, pathHealth handlers moved to useSettingsFormHandlers.ts */
  /* getTestBadge, formatTestTime, getPathBadge helpers moved or kept if solely for UI */

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

  /* isSettingsFieldDirty handled by useConfigViewModel (removed local def) */
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
      'settings-storage': ['logPath', 'snapshotPath', 'autoSave', 'intervalSec', 'statusWarnMs', 'statusOfflineMs'],
      'settings-logging': ['rotationEnabled', 'rotationMode', 'cycleIdleTime', 'cycleThresholdPress'],
      'settings-mes': ['mesEnabled', 'mesUserId', 'mesPassword', 'mesStartHour', 'mesEndHour'],
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
      intervalSec: '수집 간격 (초)',
      statusWarnMs: '경고 임계값 (ms)',
      statusOfflineMs: '오프라인 임계값 (ms)',
      mesEnabled: 'MES 연동 사용',
      mesUserId: 'MES 사용자 ID',
      mesPassword: 'MES 비밀번호',
      mesPasswordSet: 'MES 비밀번호 설정 상태',
      mesStartHour: 'MES 운영 시작 시간',
      mesEndHour: 'MES 운영 종료 시간',
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
      'intervalSec',
      'statusWarnMs',
      'statusOfflineMs',
      'mesEnabled',
      'mesUserId',
      'mesPassword',
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
      if (key === 'mesPassword') {
        if (settingsForm.mesPassword.trim()) {
          summary.push(`${labelMap.mesPassword}: 변경됨`);
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



  // Spot Logic moved to useSpotViewModel
  /* 
  useEffect(() => {
    const fetchSpotConfig = async () => { ... };
    fetchSpotConfig();
  }, []);

  useEffect(() => { ... }, [spotConfig?.image_url]);

  useEffect(() => { ... }, [spotConfig]);

  const handleSpotImageLoaded = () => { ... };

  const handleSpotImageError = (message = '이미지 수신 실패') => { ... };

  const requestFocus = async (steps: number) => { ... };
  */

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
      timeseries: () => <TimeSeriesWidget />,
      markdown: (item, model) => <MarkdownWidget item={item} model={model} />,
    };
    return getDashboardScene(registry, layoutSnapshot?.layout ?? null);
  }, [layoutSnapshot]);
  // timeSeriesDataNode dep might need removal if unused 


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

  // --- Layout Persistence (using ViewModel) ---
  /* Layout handlers moved to useLayoutHandlers.ts */
  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) return;
    const updateLayoutRef = () => {
      layoutRef.current = buildLayoutMap(grid.state.children);
    };
    updateLayoutRef();
    const sub = grid.subscribeToState(() => updateLayoutRef());
    return () => sub.unsubscribe();
  }, [scene, layoutRef]);

  const ageMs = lastDataAt ? Math.max(0, nowTick - lastDataAt) : null;
  const lastUpdateMs = health?.last_update ? health.last_update * 1000 : null;
  const healthAgeMs = lastUpdateMs ? Math.max(0, nowTick - lastUpdateMs) : null;
  const effectiveAgeMs = (healthAgeMs !== null && ageMs !== null) 
    ? Math.min(healthAgeMs, ageMs) 
    : (healthAgeMs ?? ageMs);
  const dynWarnMs = (settingsBaseline?.statusWarnMs) ? parseInt(settingsBaseline.statusWarnMs, 10) : STATUS_WARN_MS;
  const dynOfflineMs = (settingsBaseline?.statusOfflineMs) ? parseInt(settingsBaseline.statusOfflineMs, 10) : STATUS_OFFLINE_MS;
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
    // Exclude SPOT from commSeverity calculation - SPOT has its own dedicated notifications
    // Only EX and LS affect global system status
    const states = [
      buildCommBadge('EX', comm.extruder, nowTick).state,
      buildCommBadge('LS', comm.ls_plc, nowTick).state,
    ];
    if (states.includes('error')) return 'error';
    if (states.includes('warn')) return 'warn';
    return 'ok';
  })();
  let statusLabel = 'Offline';
  let statusClass = 'status-offline';
  if (effectiveAgeMs !== null) {
    if (effectiveAgeMs <= dynWarnMs) {
      statusLabel = 'Running';
      statusClass = 'status-ok';
    } else if (effectiveAgeMs <= dynOfflineMs) {
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
    
    const prev = statusRef.current;
    
    // Log status change to backend
    fetch('/api/log/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ previous: prev, current: statusLabel }),
    }).catch(() => {
      // Ignore logging errors
    });
    
    statusRef.current = statusLabel;
  }, [statusLabel]);

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

    // Status changed. Cancel any pending timer.
    if (cameraStatusTimerRef.current) {
      clearTimeout(cameraStatusTimerRef.current);
      cameraStatusTimerRef.current = null;
    }

    // Start 3-second debounce timer
    cameraStatusTimerRef.current = setTimeout(() => {
      // If we are here, status has been stable for 3 seconds
      if (type === 'error' || type === 'danger') {
        pushNotification('카메라 오류', `SPOT 카메라 ${cameraStatus?.title ?? '오류'}`, 'error');
      } else if (type === 'warn') {
        pushNotification('카메라 지연', 'SPOT 카메라 응답이 지연됩니다.', 'warn');
      } else if (type === 'ok' && cameraStatusRef.current !== 'ok') {
        pushNotification('카메라 정상', 'SPOT 카메라가 정상화되었습니다.', 'info');
      }
      // Update ref only after notification
      cameraStatusRef.current = type;
      cameraStatusTimerRef.current = null;
    }, 3000);

    return () => {
      if (cameraStatusTimerRef.current) {
        clearTimeout(cameraStatusTimerRef.current);
      }
    };
  }, [cameraStatus, pushNotification]);

  return (
    <div className={`App ${layoutEditing ? 'layout-editing' : ''}`} style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <img
            src={activeCycle === 'day' || activeCycle === 'sunset' ? '/assets/logo_color.png' : '/assets/logo_white.png'}
            alt="Company Logo"
            style={{ height: '32px', objectFit: 'contain' }}
          />
          <h1>{APP_TITLE}</h1>
        </div>
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
            onClick={() => {
              const nextState = !notificationsOpen;
              setNotificationsOpen(nextState);
              if (nextState) setUnreadCount(0);
            }}
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
                  setLayoutEditing(!layoutEditing);
                }}
              >
                {layoutEditing ? '편집 완료' : '편집 모드'}
              </button>
              {layoutEditing ? (
                <>
                  <div className="menu-dropdown-section">
                    <div className="menu-section-title">저장 위치</div>
                    <div className="menu-storage-toggle">
                      <button
                        className={`menu-item menu-storage-btn ${storageMode === 'local' ? 'active' : ''}`}
                        onClick={() => setStorageMode('local')}
                      >
                        💻 이 PC
                      </button>
                      <button
                        className={`menu-item menu-storage-btn ${storageMode === 'server' ? 'active' : ''}`}
                        onClick={() => setStorageMode('server')}
                      >
                        🖥️ 서버
                      </button>
                    </div>
                  </div>
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
                    <div className="menu-section-title">저장된 레이아웃 {storageMode === 'local' ? '(로컬)' : '(서버)'}</div>
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
                  <div className="menu-accordion">
                    <button
                      className={`menu-accordion-header ${widgetAddOpen ? 'open' : ''}`}
                      onClick={() => setWidgetAddOpen(!widgetAddOpen)}
                    >
                      <span>위젯 추가</span>
                      <span className="menu-accordion-icon">{widgetAddOpen ? '▲' : '▼'}</span>
                    </button>
                    {widgetAddOpen && (
                      <div className="menu-accordion-content">
                        <button className="menu-item" onClick={() => handleAddWidget('markdown')}>
                          📝 New Memo
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('timeseries')}>
                          📊 Time Series
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('kpi')}>
                          📈 KPI
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('spot')}>
                          🌡️ SPOT Temp
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('camera')}>
                          📷 SPOT Camera
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('temps')}>
                          🔥 Temps
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('molds')}>
                          🧊 Molds
                        </button>
                        <button className="menu-item" onClick={() => handleAddWidget('env')}>
                          🌍 Env
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="menu-divider" />
                  <div className="menu-accordion">
                    <button
                      className={`menu-accordion-header ${presetOpen ? 'open' : ''}`}
                      onClick={() => setPresetOpen(!presetOpen)}
                    >
                      <span>화면 비율 프리셋</span>
                      <span className="menu-accordion-icon">{presetOpen ? '▲' : '▼'}</span>
                    </button>
                    {presetOpen && (
                      <div className="menu-accordion-content">
                        <button className="menu-item" onClick={() => applyPreset('16:9')}>
                          📺 16:9 일반
                        </button>
                        <button className="menu-item" onClick={() => applyPreset('21:9')}>
                          🖥️ 21:9 울트라와이드
                        </button>
                        <button className="menu-item" onClick={() => applyPreset('4:3')}>
                          📟 4:3 클래식
                        </button>
                        <button className="menu-item" onClick={() => applyPreset('compact')}>
                          📱 컴팩트
                        </button>
                      </div>
                    )}
                  </div>
                </>
              ) : null}
              <div className="menu-divider" />
              <button
                className="menu-item"
                onClick={handleOpenSettings}
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
              <span className="settings-header-title">설정 (v{packageJson.version})</span>
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
                onClick={handleOverrideToggle}
                disabled={overrideBusy}
                aria-disabled={overrideBusy}
              >
                {overrideBusy ? '변경 중...' : overrideEnabled ? '오버라이드 끄기' : '오버라이드 켜기'}
              </button>
            </div>
            <div className="settings-sync-row">
              <span className="settings-sync-item">
                설정 버전: {overrideMeta?.version ?? '--'}
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
                            );
                          })}
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
                            const result = connectionTest[target.key];
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
                                  onClick={() => handleConnectionTest(target.key)}
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
                                disabled={!commLogInfo.path}
                                aria-disabled={!commLogInfo.path}
                              >
                                경로 복사
                              </button>
                              <button
                                type="button"
                                className="settings-comm-log-button"
                                onClick={handleOpenCommLogPath}
                                disabled={!commLogInfo.path}
                                aria-disabled={!commLogInfo.path}
                              >
                                폴더 열기
                              </button>
                              <button
                                type="button"
                                className="settings-comm-log-button"
                                onClick={handleOpenCommLogFile}
                                disabled={!commLogInfo.path}
                                aria-disabled={!commLogInfo.path}
                              >
                                파일 열기
                              </button>
                            </div>
                          </div>
                          <span className="settings-comm-log-value">
                            {commLogInfo.path ?? '--'}
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
                                          {formatOptionalSeconds(metrics ? metrics.last_recovery_sec : undefined)}
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
                                          {formatOptionalSeconds(metrics ? metrics.last_recovery_sec : undefined)}
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
                                          {typeof refreshMs === 'number' ? `${Math.round(refreshMs / 1000)}s` : '--'}
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
                        <div
                          className={`settings-field ${logPathFieldState} ${isSettingsFieldDirty('logPath') ? 'changed' : ''}`}
                        >
                          <label>Log Path</label>
                          <div className="settings-path-input-row">
                            <input
                              value={settingsForm.logPath}
                              onChange={(e) => updateSettingsField('logPath', e.target.value)}
                            />
                            <button
                              type="button"
                              className="settings-browse-btn"
                              onClick={async () => {
                                const selected = await browseFolder({ initial_dir: settingsForm.logPath, title: 'Log 폴더 선택' });
                                if (selected) updateSettingsField('logPath', selected);
                              }}
                            >
                              📁
                            </button>
                          </div>
                        </div>
                        <div
                          className={`settings-field ${snapshotPathFieldState} ${isSettingsFieldDirty('snapshotPath') ? 'changed' : ''}`}
                        >
                          <label>Snapshot Path</label>
                          <div className="settings-path-input-row">
                            <input
                              value={settingsForm.snapshotPath}
                              onChange={(e) => updateSettingsField('snapshotPath', e.target.value)}
                            />
                            <button
                              type="button"
                              className="settings-browse-btn"
                              onClick={async () => {
                                const selected = await browseFolder({ initial_dir: settingsForm.snapshotPath, title: 'Snapshot 폴더 선택' });
                                if (selected) updateSettingsField('snapshotPath', selected);
                              }}
                            >
                              📁
                            </button>
                          </div>
                        </div>
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
                        
                        {/* Interval Collection Settings */}
                        <div className={`settings-field settings-interval-field ${isSettingsFieldDirty('intervalSec') ? 'changed' : ''}`}>
                          <label>수집 간격 (초)</label>
                          <div className="settings-interval-row">
                            <div className="settings-interval-presets">
                              {[0.1, 0.2, 0.5, 1.0].map((preset) => (
                                <button
                                  key={preset}
                                  type="button"
                                  className={`settings-preset-btn ${parseFloat(settingsForm.intervalSec) === preset ? 'active' : ''}`}
                                  onClick={() => updateSettingsField('intervalSec', preset.toString())}
                                >
                                  {preset}s
                                </button>
                              ))}
                            </div>
                            <input
                              type="number"
                              min="0.1"
                              max="2.0"
                              step="0.1"
                              value={settingsForm.intervalSec}
                              onChange={(e) => updateSettingsField('intervalSec', e.target.value)}
                              className="settings-interval-input"
                            />
                          </div>
                          <div className="settings-interval-preview">
                            {(() => {
                              const interval = parseFloat(settingsForm.intervalSec) || 0.2;
                              const pointsPerHour = Math.round(3600 / interval);
                              const mbPerHour = (pointsPerHour * 150 / 1024 / 1024).toFixed(1);
                              return (
                                <span className="settings-interval-hint">
                                  📊 예상: {pointsPerHour.toLocaleString()}포인트/h • ~{mbPerHour}MB/h
                                </span>
                              );
                            })()}
                          </div>
                        </div>

                        {/* Status Threshold Settings */}
                        <div className="settings-system-thresholds">
                          <label
                            className={`settings-field ${isSettingsFieldDirty('statusWarnMs') ? 'changed' : ''} ${validationErrors.statusWarnMs ? 'error' : ''}`}
                          >
                            상태 경고 임계값 (ms)
                            <input
                              type="number"
                              step="500"
                              min="1000"
                              value={settingsForm.statusWarnMs}
                              onChange={(e) => updateSettingsField('statusWarnMs', e.target.value)}
                            />
                            <span className="settings-field-help">통신 지연이 이 시간을 초과하면 'Warning'으로 표시됩니다.</span>
                          </label>
                          <label
                            className={`settings-field ${isSettingsFieldDirty('statusOfflineMs') ? 'changed' : ''} ${validationErrors.statusOfflineMs ? 'error' : ''}`}
                          >
                            오프라인 임계값 (ms)
                            <input
                              type="number"
                              step="1000"
                              min="2000"
                              value={settingsForm.statusOfflineMs}
                              onChange={(e) => updateSettingsField('statusOfflineMs', e.target.value)}
                            />
                            <span className="settings-field-help">통신 지연이 이 시간을 초과하면 'Offline'으로 표시됩니다.</span>
                          </label>
                        </div>
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
                                    onClick={() => handleCreatePath(pathValue)}
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
                      id="settings-mes"
                      ref={registerSettingsSection('settings-mes')}
                    >
                      <div className="settings-section-title">MES 설정</div>
                      <div className="settings-grid">
                        <label
                          className={`settings-field settings-toggle-field ${isSettingsFieldDirty('mesEnabled') ? 'changed' : ''}`}
                        >
                          <span className="settings-toggle-label">MES 연동 사용</span>
                          <button
                            type="button"
                            className="settings-toggle"
                            aria-pressed={settingsForm.mesEnabled}
                            onClick={() => updateSettingsField('mesEnabled', !settingsForm.mesEnabled)}
                          >
                            <span className="settings-toggle-text">{settingsForm.mesEnabled ? 'ON' : 'OFF'}</span>
                          </button>
                        </label>
                        <label className={`settings-field ${isSettingsFieldDirty('mesUserId') ? 'changed' : ''}`}>
                          MES User ID
                          <input
                            value={settingsForm.mesUserId}
                            onChange={(e) => updateSettingsField('mesUserId', e.target.value)}
                            placeholder="UserID"
                          />
                        </label>
                        <label className={`settings-field ${isSettingsFieldDirty('mesPassword') ? 'changed' : ''}`}>
                          MES Password
                          <input
                            type="password"
                            value={settingsForm.mesPassword}
                            onChange={(e) => updateSettingsField('mesPassword', e.target.value)}
                            placeholder={settingsForm.mesPasswordSet ? "********" : "비밀번호 입력"}
                          />
                          <span className="settings-field-help">
                            {settingsForm.mesPasswordSet ? "비밀번호가 설정되어 있습니다. 변경 시에만 입력하세요." : "MES 연동을 위해 비밀번호를 입력하세요."}
                          </span>
                        </label>
                        <label className={`settings-field ${isSettingsFieldDirty('mesStartHour') ? 'changed' : ''}`}>
                          운영 시작 시간
                          <input
                            type="number"
                            min="0"
                            max="23"
                            value={settingsForm.mesStartHour}
                            onChange={(e) => updateSettingsField('mesStartHour', e.target.value)}
                          />
                          <span className="settings-field-help">시 (0~23)</span>
                        </label>
                        <label className={`settings-field ${isSettingsFieldDirty('mesEndHour') ? 'changed' : ''}`}>
                          운영 종료 시간
                          <input
                            type="number"
                            min="0"
                            max="23"
                            value={settingsForm.mesEndHour}
                            onChange={(e) => updateSettingsField('mesEndHour', e.target.value)}
                          />
                          <span className="settings-field-help">시 (0~23)</span>
                        </label>

                      </div>
                      <div className="settings-hint">
                        MES 연동을 활성화하면 수집된 데이터를 실시간으로 MES 서버에 전송합니다. 운영 시간 외에는 수집이 일시 중지됩니다.
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
                      
                      {/* Warning Banner when password not set */}
                      {!settingsForm.passwordSet && (
                        <div className="settings-warning" style={{ marginBottom: '12px', backgroundColor: 'rgba(255, 193, 7, 0.15)', border: '1px solid rgba(255, 193, 7, 0.4)', borderRadius: '6px', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                          <span>보안을 위해 설정 비밀번호를 등록하세요. 미설정 시 누구나 설정에 접근할 수 있습니다.</span>
                        </div>
                      )}
                      
                      <div className="settings-grid">
                        {/* Current Password (shown first when password is already set) */}
                        {settingsForm.passwordSet && (
                          <label className="settings-field">
                            현재 비밀번호
                            <div style={{ position: 'relative' }}>
                              <input
                                type={showCurrentPassword ? 'text' : 'password'}
                                placeholder="현재 비밀번호 입력"
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                                style={{ paddingRight: '40px' }}
                              />
                              <button
                                type="button"
                                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                                style={{
                                  position: 'absolute',
                                  right: '8px',
                                  top: '50%',
                                  transform: 'translateY(-50%)',
                                  background: 'none',
                                  border: 'none',
                                  cursor: 'pointer',
                                  padding: '4px',
                                  opacity: 0.7,
                                  fontSize: '1rem'
                                }}
                                title={showCurrentPassword ? '숨기기' : '표시'}
                              >
                                {showCurrentPassword ? '🙈' : '👁️'}
                              </button>
                            </div>
                            <span className="settings-field-help">비밀번호를 변경하려면 현재 비밀번호를 먼저 입력하세요.</span>
                          </label>
                        )}
                        
                        {/* New Password - only enable input when current password is provided (if password was set) */}
                        <label className={`settings-field ${isSettingsFieldDirty('password') ? 'changed' : ''}`}>
                          {settingsForm.passwordSet ? '새 비밀번호' : '설정 비밀번호'}
                          <div style={{ position: 'relative' }}>
                            <input
                              type={showNewPassword ? 'text' : 'password'}
                              placeholder={settingsForm.passwordSet ? '새 비밀번호 입력 (변경 시에만)' : '비밀번호 입력'}
                              value={settingsForm.password}
                              onChange={(e) => updateSettingsField('password', e.target.value)}
                              disabled={settingsForm.passwordSet && currentPassword.trim().length === 0}
                              style={{ 
                                paddingRight: '40px',
                                opacity: settingsForm.passwordSet && currentPassword.trim().length === 0 ? 0.6 : 1
                              }}
                            />
                            <button
                              type="button"
                              onClick={() => setShowNewPassword(!showNewPassword)}
                              style={{
                                position: 'absolute',
                                right: '8px',
                                top: '50%',
                                transform: 'translateY(-50%)',
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                padding: '4px',
                                opacity: 0.7,
                                fontSize: '1rem'
                              }}
                              title={showNewPassword ? '숨기기' : '표시'}
                            >
                              {showNewPassword ? '🙈' : '👁️'}
                            </button>
                          </div>
                          
                          {/* Password Strength Indicator */}
                          {settingsForm.password.trim().length > 0 && (
                            <div style={{ marginTop: '6px' }}>
                              <div style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
                                {[1, 2, 3].map((level) => {
                                  const strength = (() => {
                                    const pw = settingsForm.password.trim();
                                    if (pw.length < 4) return 1;
                                    if (pw.length < 8) return 2;
                                    return 3;
                                  })();
                                  const active = level <= strength;
                                  const colors = ['#ef4444', '#f59e0b', '#22c55e'];
                                  return (
                                    <div
                                      key={level}
                                      style={{
                                        flex: 1,
                                        height: '4px',
                                        borderRadius: '2px',
                                        backgroundColor: active ? colors[strength - 1] : 'var(--border-muted)',
                                        transition: 'background-color 0.2s'
                                      }}
                                    />
                                  );
                                })}
                              </div>
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                {(() => {
                                  const pw = settingsForm.password.trim();
                                  if (pw.length < 4) return '강도: 약함 (4자 이상 권장)';
                                  if (pw.length < 8) return '강도: 보통 (8자 이상 권장)';
                                  return '강도: 강함';
                                })()}
                              </span>
                            </div>
                          )}
                        </label>
                        
                        {/* Password Confirmation */}
                        {settingsForm.password.trim().length > 0 && (
                          <label className="settings-field">
                            비밀번호 확인
                            <div style={{ position: 'relative' }}>
                              <input
                                type={showConfirmPassword ? 'text' : 'password'}
                                placeholder="비밀번호 재입력"
                                value={passwordConfirm}
                                onChange={(e) => setPasswordConfirm(e.target.value)}
                                style={{ 
                                  paddingRight: '40px',
                                  borderColor: passwordConfirm.length > 0 && passwordConfirm !== settingsForm.password ? '#ef4444' : undefined
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                style={{
                                  position: 'absolute',
                                  right: '8px',
                                  top: '50%',
                                  transform: 'translateY(-50%)',
                                  background: 'none',
                                  border: 'none',
                                  cursor: 'pointer',
                                  padding: '4px',
                                  opacity: 0.7,
                                  fontSize: '1rem'
                                }}
                                title={showConfirmPassword ? '숨기기' : '표시'}
                              >
                                {showConfirmPassword ? '🙈' : '👁️'}
                              </button>
                            </div>
                            {passwordConfirm.length > 0 && passwordConfirm !== settingsForm.password && (
                              <span className="settings-field-help error">비밀번호가 일치하지 않습니다.</span>
                            )}
                            {passwordConfirm.length > 0 && passwordConfirm === settingsForm.password && (
                              <span className="settings-field-help" style={{ color: '#22c55e' }}>✓ 비밀번호 일치</span>
                            )}
                          </label>
                        )}
                        
                        <div className="settings-hint">
                          {settingsForm.passwordSet 
                            ? '비밀번호를 변경하려면 현재 비밀번호 입력 후 새 비밀번호를 입력하세요. 비워두면 기존 비밀번호를 유지합니다.'
                            : '설정에 접근할 때 사용할 비밀번호를 설정하세요.'}
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
        <FactoryDataContext.Provider
          value={{
            data,
            thresholds: thresholdState,
            lastDataAt,
            nowTick,
            intervalSec: parseFloat(settingsForm?.intervalSec ?? '0.2') || 0.2,
            timeSeriesFrames,
            timeSeriesAllFrame,
          }}
        >
          <SpotContext.Provider
            value={{
              spotConfig,
              spotImageUrl,
              spotImageLoading,
              spotImageError,
              spotLastSuccessAt,
              spotAlertActive,
              onSpotImageLoaded: handleSpotImageLoaded,
              onSpotImageError: handleSpotImageError,
              requestFocus,
            }}
          >
            <UIContext.Provider
              value={{
                seriesWindowMin,
                seriesPaused,
                showThresholds,
                layoutEditing,
                setSeriesWindowMin,
                setSeriesPaused,
                setShowThresholds,
                setLayoutEditing,
              }}
            >
              <SnapshotContext.Provider
                value={{
                  handleSnapshot,
                  snapshotLoading,
                }}
              >
                <LayoutEditContext.Provider value={{ isEditing: layoutEditing, deleteWidget: handleRemoveWidget, updateWidget: handleUpdateWidget }}>
                  <scene.Component model={scene} />
                </LayoutEditContext.Provider>
              </SnapshotContext.Provider>
            </UIContext.Provider>
          </SpotContext.Provider>
        </FactoryDataContext.Provider>
        <footer className="app-footer">
          Copyright © HOIHOU. All Rights Reserved. v{packageJson.version}
        </footer>
      </div>
    </div>
  );
}

export default App;

