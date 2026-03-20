import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import ReactMarkdown from 'react-markdown';
import {
  SpotConfig,
  HealthSnapshot,
  StatsSnapshot,
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
  CentralStatus,
  CentralSyncResult,
  LayoutSnapshot,
  LayoutSlotSummary,
  LayoutMap
} from './shared/types';
import { useSystemViewModel } from './domains/Observability/hooks/useSystemViewModel';
import { useMemoryViewModel } from './domains/Observability/hooks/useMemoryViewModel';
import { useSpotViewModel } from './domains/FacilityData/hooks/useSpotViewModel';
import { useConfigViewModel } from './domains/Configuration/hooks/useConfigViewModel';
import { useLayoutViewModel } from './domains/Configuration/hooks/useLayoutViewModel';
import { useMetricsViewModel } from './domains/FacilityData/hooks/useMetricsViewModel';
import { useViewportScale, applyRowHeightToCSS } from './domains/Configuration/hooks/useViewportScale';
import { useStatusPanel } from './domains/Layout/hooks/useStatusPanel';
import { DashboardHeader } from './domains/Layout/components/DashboardHeader/DashboardHeader';
import { NotificationDrawer } from './domains/Layout/components/NotificationDrawer';
import './App.css';
import packageJson from '../package.json';
const UPlotChart = React.lazy(() => import('./domains/FacilityData/components/UPlotChart').then(m => ({ default: m.UPlotChart })));
import type uPlot from 'uplot';

// --- Widget Imports ---
import { KpiComponent } from './domains/FacilityData/components/widgets/KpiWidget';
import { SpotComponent } from './domains/FacilityData/components/widgets/SpotWidget';
const TempsComponent = React.lazy(() => import('./domains/FacilityData/components/widgets/TempsWidget').then(m => ({ default: m.TempsComponent })));
const MoldsComponent = React.lazy(() => import('./domains/FacilityData/components/widgets/MoldsWidget').then(m => ({ default: m.MoldsComponent })));
const EnvComponent = React.lazy(() => import('./domains/FacilityData/components/widgets/EnvWidget').then(m => ({ default: m.EnvComponent })));
const CameraComponent = React.lazy(() => import('./domains/FacilityData/components/widgets/CameraWidget').then(m => ({ default: m.CameraComponent })));
const TimeSeriesWidget = React.lazy(() => import('./domains/FacilityData/components/widgets/TimeSeriesWidget').then(m => ({ default: m.TimeSeriesWidget })));

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
import {
  getTestBadge,
  formatTestTime,
  getPathBadge,
  formatPathCheckTime,
  formatPathMessage,
  getCentralBadge,
  formatCentralTime,
} from './domains/Configuration/components/SettingsModal/settingsModalHelpers';
import { useSettingsModalState } from './domains/Configuration/components/SettingsModal/useSettingsModalState';
import { SettingsModal } from './domains/Configuration/components/SettingsModal/SettingsModal';

// Initialize Scenes Runtime (guarded for HMR)
if (typeof window !== 'undefined') {
  if (!(window as any).__SCENES_INIT__) {
    initScenesRuntime();
    (window as any).__SCENES_INIT__ = true;
  }
} else {
  initScenesRuntime();
}

import { safeGetItem, safeSetItem, safeRemoveItem } from './shared/utils/safeStorage';

import { apiClient, API_BASE } from './shared/api/client';
import { configService } from './domains/Configuration/api/configService';
// Data Contexts
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
      const saved = safeGetItem('seriesWindowMin');
      return saved ? parseInt(saved, 10) : 30;
    } catch { return 30; }
  });
  const setSeriesWindowMin = useCallback((min: number) => {
    setSeriesWindowMinState(min);
    safeSetItem('seriesWindowMin', String(min));
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
    healthPolling,
    statsPolling,
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
    diagnostics: spotDiagnostics,
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
    pollingDegraded,
    pollingIntervalMs,
    pollingFailureCount,
    timeSeriesFrames,
    timeSeriesAllFrame,
    getSeriesSamples,
    getSeriesStats,
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
      const raw = safeGetItem(FRONT_ERROR_STORAGE_KEY);
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
    safeSetItem(FRONT_ERROR_STORAGE_KEY, JSON.stringify(items));
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
        safeRemoveItem(FRONT_ERROR_STORAGE_KEY);
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
      { id: 'settings-memory', label: '메모리' },
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

  const {
    backendMemory,
    backendMemoryDetails,
    frontendMemory,
    memorySummaryBusy,
    memoryDetailsBusy,
    memoryRefreshInFlight,
    memoryRefreshIntervalMs,
    profilerStartBusy,
    profilerStopBusy,
    memoryExportBusy,
    memoryExportPath,
    memoryLeader,
    memoryActionState,
    lastExportAt,
    lastSummaryAt,
    lastDetailsAt,
    lastExportMetaAt,
    summaryRequestCount,
    detailsRequestCount,
    lastSummaryReason,
    refreshMemory,
    startMemoryProfiler,
    stopMemoryProfiler,
    captureMemorySnapshot,
    exportMemory,
    openMemoryExportFile,
    openMemoryExportFolder,
    copyMemoryExportPath,
  } = useMemoryViewModel({
    enabled: settingsOpen && activeSettingsSection === 'settings-memory',
    seriesStats: getSeriesStats(),
    timeSeriesFrames,
    timeSeriesAllFrame,
    layoutSnapshot,
    observabilityErrors,
    frontErrors,
    spotImageUrl,
    spotDiagnostics,
    settingsForm,
    settingsPending,
    externalConfigPending,
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



  const {
    settingsDirtyCount,
    settingsSectionFieldMap,
    settingsSectionHasChanges,
    buildSettingsSummaryCards,
    buildSettingsChangeSummary,
    hasPathError,
    hasPathWarn,
    logPathFieldState,
    snapshotPathFieldState,
    applyDetails,
  } = useSettingsModalState({
    settingsForm,
    settingsBaseline,
    settingsApplyResult,
    overrideMeta,
    pathHealth,
    hasSettingsChanges,
    isSettingsFieldDirty,
  });

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
  const handleRefreshMemory = useCallback(async () => {
    try {
      await refreshMemory();
      showSettingsToast('메모리 상태를 새로고침했습니다.', 'ok');
    } catch (error) {
      console.error('Memory refresh failed', error);
      showSettingsToast('메모리 상태 새로고침에 실패했습니다.', 'error');
    }
  }, [refreshMemory, showSettingsToast]);

  const handleStartMemoryProfiler = useCallback(async () => {
    try {
      await startMemoryProfiler();
      showSettingsToast('상세 메모리 추적을 시작했습니다.', 'ok');
    } catch (error) {
      console.error('Memory profiler start failed', error);
      showSettingsToast('상세 메모리 추적 시작에 실패했습니다.', 'error');
    }
  }, [showSettingsToast, startMemoryProfiler]);

  const handleStopMemoryProfiler = useCallback(async () => {
    try {
      await stopMemoryProfiler();
      showSettingsToast('상세 메모리 추적을 중지했습니다.', 'ok');
    } catch (error) {
      console.error('Memory profiler stop failed', error);
      showSettingsToast('상세 메모리 추적 중지에 실패했습니다.', 'error');
    }
  }, [showSettingsToast, stopMemoryProfiler]);

  const handleCaptureMemorySnapshot = useCallback(async () => {
    try {
      await captureMemorySnapshot();
      showSettingsToast('메모리 스냅샷을 수집했습니다.', 'ok');
    } catch (error) {
      console.error('Memory snapshot failed', error);
      showSettingsToast('메모리 스냅샷 수집에 실패했습니다.', 'error');
    }
  }, [captureMemorySnapshot, showSettingsToast]);

  const handleExportMemory = useCallback(async () => {
    try {
      const path = await exportMemory();
      if (!path) {
        throw new Error('Memory export path missing');
      }
      showSettingsToast('메모리 진단 파일을 저장했습니다.', 'ok');
    } catch (error) {
      console.error('Memory export failed', error);
      showSettingsToast('메모리 진단 파일 저장에 실패했습니다.', 'error');
    }
  }, [exportMemory, showSettingsToast]);

  const handleOpenMemoryExportFile = useCallback(async () => {
    try {
      await openMemoryExportFile();
    } catch (error) {
      console.error('Open memory export file failed', error);
      showSettingsToast('메모리 export 파일 열기에 실패했습니다.', 'error');
    }
  }, [openMemoryExportFile, showSettingsToast]);

  const handleOpenMemoryExportFolder = useCallback(async () => {
    try {
      await openMemoryExportFolder();
    } catch (error) {
      console.error('Open memory export folder failed', error);
      showSettingsToast('메모리 export 폴더 열기에 실패했습니다.', 'error');
    }
  }, [openMemoryExportFolder, showSettingsToast]);

  const handleCopyMemoryExportPath = useCallback(async () => {
    try {
      await copyMemoryExportPath();
      showSettingsToast('메모리 export 경로를 복사했습니다.', 'ok');
    } catch (error) {
      console.error('Copy memory export path failed', error);
      showSettingsToast('메모리 export 경로 복사에 실패했습니다.', 'error');
    }
  }, [copyMemoryExportPath, showSettingsToast]);


  // --- Widget Renderers ---
  // --- Scene Creation ---
  // Scene is created once; widget data is read from DataContext.
  const scene = useMemo(() => {
    const registry: WidgetRegistry = {
      kpi: () => <KpiComponent />,
      spot: () => <SpotComponent />,
      temps: () => (
        <React.Suspense fallback={<div className="widget-loading">Loading...</div>}>
          <TempsComponent />
        </React.Suspense>
      ),
      camera: () => (
        <React.Suspense fallback={<div className="widget-loading">Loading...</div>}>
          <CameraComponent
            onSpotImageLoaded={handleSpotImageLoaded}
            onSpotImageError={handleSpotImageError}
            requestFocus={requestFocus}
            focusBusy={focusBusy}
          />
        </React.Suspense>
      ),
      molds: () => (
        <React.Suspense fallback={<div className="widget-loading">Loading...</div>}>
          <MoldsComponent />
        </React.Suspense>
      ),
      env: () => (
        <React.Suspense fallback={<div className="widget-loading">Loading...</div>}>
          <EnvComponent />
        </React.Suspense>
      ),
      timeseries: () => (
        <React.Suspense fallback={<div className="widget-loading">Loading...</div>}>
          <TimeSeriesWidget />
        </React.Suspense>
      ),
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

  // --- Status Panel Data Extraction (Phase 12 Step 4) ---
  const {
    statusLabel,
    statusClass,
    statusTitle,
    lastUpdateText,
    avgLatencyText,
    errorCountText,
    errorQueueText,
    errorQueueTitle,
    commSnapshot,
    commBadges,
    commDetail,
    commSummaryItems,
    statsWindow,
    windowErrorRate,
    hasWindowIssue,
    windowP95Text,
    errorQueueSize,
    lastErrorAt,
    cameraStatus,
  } = useStatusPanel({
    health,
    stats,
    nowTick,
    lastDataAt,
    connected,
    dataPollingDegraded: pollingDegraded,
    dataPollingIntervalMs: pollingIntervalMs,
    dataPollingFailureCount: pollingFailureCount,
    healthPollingDegraded: healthPolling.degraded,
    healthPollingIntervalMs: healthPolling.intervalMs,
    healthPollingFailureCount: healthPolling.failureCount,
    statsPollingDegraded: statsPolling.degraded,
    statsPollingIntervalMs: statsPolling.intervalMs,
    statsPollingFailureCount: statsPolling.failureCount,
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    settingsBaseline,
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

  // FactoryDataContext and SpotContext values have been removed.

  const uiContextValue = useMemo(() => ({
    seriesWindowMin,
    seriesPaused,
    showThresholds,
    layoutEditing,
    setSeriesWindowMin,
    setSeriesPaused,
    setShowThresholds,
    setLayoutEditing,
  }), [seriesWindowMin, seriesPaused, showThresholds, layoutEditing, setSeriesWindowMin, setSeriesPaused, setShowThresholds, setLayoutEditing]);

  const snapshotContextValue = useMemo(() => ({
    handleSnapshot,
    snapshotLoading,
  }), [handleSnapshot, snapshotLoading]);

  const layoutEditContextValue = useMemo(() => ({
    isEditing: layoutEditing,
    deleteWidget: handleRemoveWidget,
    updateWidget: handleUpdateWidget
  }), [layoutEditing, handleRemoveWidget, handleUpdateWidget]);

  const SceneRenderer = useMemo(() => <scene.Component model={scene} />, [scene]);

  return (
    <div className={`App ${layoutEditing ? 'layout-editing' : ''}`} style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <DashboardHeader
        activeCycle={activeCycle}
        statusLabel={statusLabel}
        statusClass={statusClass}
        statusTitle={statusTitle}
        lastUpdateText={lastUpdateText}
        avgLatencyText={avgLatencyText}
        errorCountText={errorCountText}
        errorQueueText={errorQueueText}
        errorQueueTitle={errorQueueTitle}
        commBadges={commBadges}
        handleSnapshot={handleSnapshot}
        snapshotLoading={snapshotLoading}
        handleReconnect={handleReconnect}
        reconnectBusy={reconnectBusy}
        handleDiagnosis={handleDiagnosis}
        diagnosisBusy={diagnosisBusy}
        settingsForm={settingsForm}
        unreadCount={unreadCount}
        notificationsOpen={notificationsOpen}
        setNotificationsOpen={setNotificationsOpen}
        setUnreadCount={setUnreadCount}
        clearNotifications={clearNotifications}
        menuOpen={menuOpen}
        setMenuOpen={setMenuOpen}
        menuRef={menuRef}
        widgetAddOpen={widgetAddOpen}
        setWidgetAddOpen={setWidgetAddOpen}
        presetOpen={presetOpen}
        setPresetOpen={setPresetOpen}
        layoutEditing={layoutEditing}
        setLayoutEditing={setLayoutEditing}
        storageMode={storageMode}
        setStorageMode={setStorageMode}
        saveLayout={saveLayout}
        restoreLayout={restoreLayout}
        deleteLayoutSlot={deleteLayoutSlot}
        layoutSlots={layoutSlots}
        layoutActiveId={layoutActiveId}
        layoutRestoreMessage={layoutRestoreMessage}
        layoutSaveMessage={layoutSaveMessage}
        layoutSaveError={layoutSaveError}
        layoutRestoreError={layoutRestoreError}
        handleAddWidget={handleAddWidget}
        applyPreset={applyPreset}
        themeMode={mode}
        setThemeMode={setMode}
        handleOpenSettings={handleOpenSettings}
      />
      <NotificationDrawer
        notifications={notifications}
        notificationsOpen={notificationsOpen}
        setNotificationsOpen={setNotificationsOpen}
        clearNotifications={clearNotifications}
      />
      <SettingsModal
        settingsOpen={settingsOpen}
        setSettingsOpen={setSettingsOpen}
        settingsLoading={settingsLoading}
        settingsError={settingsError}
        settingsInfo={settingsInfo}
        settingsForm={settingsForm}
        settingsBaseline={settingsBaseline}
        settingsConfigPath={settingsConfigPath}
        settingsRestartRequired={settingsRestartRequired}
        settingsApplyResult={settingsApplyResult}
        settingsPending={settingsPending}
        settingsPendingBusy={settingsPendingBusy}
        settingsToast={settingsToast}
        hasSettingsChanges={hasSettingsChanges}
        validationErrors={validationErrors}
        hasValidationError={hasValidationError}
        configReadOnly={configReadOnly}
        overrideEnabled={overrideEnabled}
        overrideMeta={overrideMeta}
        overrideBusy={overrideBusy}
        centralStatus={centralStatus}
        centralSyncBusy={centralSyncBusy}
        externalConfigPending={externalConfigPending}
        externalConfigPendingAt={externalConfigPendingAt}
        updateSettingsField={updateSettingsField}
        handleSaveSettings={handleSaveSettings}
        handleRestoreDefaults={handleRestoreDefaults}
        handleRestoreBackup={handleRestoreBackup}
        handleOverrideToggle={handleOverrideToggle}
        handleMasterToggle={handleMasterToggle}
        handlePendingApply={handlePendingApply}
        handlePendingClear={handlePendingClear}
        handleExternalRefresh={handleExternalRefresh}
        handleExternalIgnore={handleExternalIgnore}
        handleCentralSync={handleCentralSync}
        isSettingsFieldDirty={isSettingsFieldDirty}
        settingsDirtyCount={settingsDirtyCount}
        settingsSectionFieldMap={settingsSectionFieldMap}
        settingsSectionHasChanges={settingsSectionHasChanges}
        buildSettingsSummaryCards={buildSettingsSummaryCards}
        buildSettingsChangeSummary={buildSettingsChangeSummary}
        applyDetails={applyDetails}
        settingsSections={settingsSections}
        activeSettingsSection={activeSettingsSection}
        scrollToSettingsSection={scrollToSettingsSection}
        registerSettingsSection={registerSettingsSection}
        settingsScrollRef={settingsScrollRef}
        connectionTest={connectionTest}
        connectionTestBusy={connectionTestBusy}
        connectionTestTargets={connectionTestTargets}
        handleConnectionTest={handleConnectionTest}
        pathHealth={pathHealth}
        pathCheckBusy={pathCheckBusy}
        hasPathError={hasPathError}
        hasPathWarn={hasPathWarn}
        logPathFieldState={logPathFieldState}
        snapshotPathFieldState={snapshotPathFieldState}
        runPathHealthCheck={runPathHealthCheck}
        handleCreatePath={handleCreatePath}
        browseFolder={browseFolder}
        health={health}
        stats={stats}
        observabilityErrors={observabilityErrors}
        observabilityLoading={observabilityLoading}
        loadObservabilityErrors={loadObservabilityErrors}
        handleExportObservability={handleExportObservability}
        handleOpenObservabilityExportFile={handleOpenObservabilityExportFile}
        handleOpenObservabilityExportFolder={handleOpenObservabilityExportFolder}
        handleCopyObservabilityExportPath={handleCopyObservabilityExportPath}
        handleClearObservabilityErrors={handleClearObservabilityErrors}
        lastExportPath={lastExportPath}
        exportBusy={exportBusy}
        backendMemory={backendMemory}
        backendMemoryDetails={backendMemoryDetails}
        frontendMemory={frontendMemory}
        memorySummaryBusy={memorySummaryBusy}
        memoryDetailsBusy={memoryDetailsBusy}
        memoryRefreshInFlight={memoryRefreshInFlight}
        memoryRefreshIntervalMs={memoryRefreshIntervalMs}
        profilerStartBusy={profilerStartBusy}
        profilerStopBusy={profilerStopBusy}
        memoryExportBusy={memoryExportBusy}
        memoryExportPath={memoryExportPath}
        memoryLeader={memoryLeader}
        memoryActionState={memoryActionState}
        lastExportAt={lastExportAt}
        lastSummaryAt={lastSummaryAt}
        lastDetailsAt={lastDetailsAt}
        lastExportMetaAt={lastExportMetaAt}
        summaryRequestCount={summaryRequestCount}
        detailsRequestCount={detailsRequestCount}
        lastSummaryReason={lastSummaryReason}
        handleRefreshMemory={handleRefreshMemory}
        handleStartMemoryProfiler={handleStartMemoryProfiler}
        handleStopMemoryProfiler={handleStopMemoryProfiler}
        handleCaptureMemorySnapshot={handleCaptureMemorySnapshot}
        handleExportMemory={handleExportMemory}
        handleOpenMemoryExportFile={handleOpenMemoryExportFile}
        handleOpenMemoryExportFolder={handleOpenMemoryExportFolder}
        handleCopyMemoryExportPath={handleCopyMemoryExportPath}
        spotConfig={spotConfig}
        spotImageUrl={spotImageUrl}
        spotImageLoading={spotImageLoading}
        spotLastSuccessAt={spotLastSuccessAt}
        spotDiagnostics={spotDiagnostics}
        commLogInfo={commLogInfo}
        handleOpenCommLogPath={handleOpenCommLogPath}
        handleOpenCommLogFile={handleOpenCommLogFile}
        handleCopyCommLogPath={handleCopyCommLogPath}
        frontErrors={frontErrors}
        clearFrontErrors={clearFrontErrors}
        currentPassword={currentPassword}
        setCurrentPassword={setCurrentPassword}
        passwordConfirm={passwordConfirm}
        setPasswordConfirm={setPasswordConfirm}
        showCurrentPassword={showCurrentPassword}
        setShowCurrentPassword={setShowCurrentPassword}
        showNewPassword={showNewPassword}
        setShowNewPassword={setShowNewPassword}
        showConfirmPassword={showConfirmPassword}
        setShowConfirmPassword={setShowConfirmPassword}
        thresholdItems={thresholdItems}
        thresholdState={thresholdState}
        getCameraStatus={getCameraStatus}
        nowTick={nowTick}
        commSnapshot={commSnapshot}
        commDetail={commDetail}
        commSummaryItems={commSummaryItems}
        statsWindow={statsWindow}
        windowErrorRate={windowErrorRate}
        hasWindowIssue={hasWindowIssue}
        windowP95Text={windowP95Text}
        errorQueueSize={errorQueueSize}
        errorQueueText={errorQueueText}
        lastErrorAt={lastErrorAt}
        spotImageError={spotImageError}
        showSettingsToast={showSettingsToast}
      />
      <div className="scene-container" style={{ flexGrow: 1 }}>
        {/* The ReactWidget will be rendered *inside* this provider hierarchy. */}
        <UIContext.Provider value={uiContextValue}>
          <SnapshotContext.Provider value={snapshotContextValue}>
            <LayoutEditContext.Provider value={layoutEditContextValue}>
              {SceneRenderer}
            </LayoutEditContext.Provider>
          </SnapshotContext.Provider>
        </UIContext.Provider>
        <footer className="app-footer">
          Copyright © HOIHOU. All Rights Reserved. v{packageJson.version}
        </footer>
      </div>
    </div>
  );
}

export default App;
