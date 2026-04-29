import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  SpotConfig,
  HealthSnapshot,
  StatsSnapshot,
  ConfigUpdateResponse,
  ThresholdEntry,
  FrontendErrorEntry,
  NotificationLevel,
  NotificationItem,
  CentralStatus,
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
import { useStatusPanel } from './domains/Layout/hooks/useStatusPanel';
import { DashboardHeader } from './domains/Layout/components/DashboardHeader/DashboardHeader';
import { LayoutEditContext } from './domains/Configuration/context/LayoutEditContext';
import { AIChatbotLauncher } from './AI/components/AIChatbotLauncher';
import './App.css';
import packageJson from '../package.json';
const NotificationDrawer = React.lazy(() => import('./domains/Layout/components/NotificationDrawer').then(m => ({ default: m.NotificationDrawer })));

// --- Widget Imports ---
// UPlot Series Colors Mapping - Moved to seriesCatalog.ts
import { SERIES_COLORS } from './domains/FacilityData/timeseries/seriesCatalog';

import { buildSeriesThresholds } from './domains/FacilityData/timeseries/seriesThresholds';
import {
  APP_TITLE,
  NOTICE_BODY_PREFIX,
  NOTICE_BODY_SUFFIX,
  NOTICE_FOOTER,
  NOTICE_TEMP_THRESHOLD,
  NOTICE_TITLE,
} from './shared/constants/uiText';
import * as LOGIC from './shared/constants/logic';
import * as THEME from './shared/constants/theme';
import { useModal } from './shared/hooks/useGlobalModalContext';
import { useTheme } from './shared/hooks/useThemeContext';

const MAX_NOTIFICATIONS = 50;

const SettingsModalContainer = React.lazy(() => import('./domains/Configuration/components/SettingsModal/SettingsModalContainer').then(m => ({ default: m.SettingsModalContainer })));
const DashboardSceneSurface = React.lazy(() => import('./scenes/DashboardSceneSurface').then(m => ({ default: m.DashboardSceneSurface })));
const NativeDashboardSurface = React.lazy(() => import('./scenes/NativeDashboardSurface').then(m => ({ default: m.NativeDashboardSurface })));

import { safeGetItem, safeSetItem, safeRemoveItem } from './shared/utils/safeStorage';

import { apiClient, API_BASE } from './shared/api/client';
import { configService } from './domains/Configuration/api/configService';
// Data Contexts
import { UIContext } from './domains/FacilityData/context/UIContext';
import { DataContext } from './domains/FacilityData/context/DataContext';
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

const hasLayoutTimeSeriesWidget = (layout: LayoutMap | null): boolean => {
  if (!layout) {
    return true;
  }

  return Object.values(layout).some((item) => item.type === 'timeseries');
};

const LazyModalFallback = ({ title }: { title: string }): JSX.Element => (
  <div className="custom-modal-overlay">
    <div className="custom-modal-content">
      <div className="custom-modal-header">
        <div className="custom-modal-title">{title}</div>
      </div>
      <div className="custom-modal-body">로딩 중입니다.</div>
    </div>
  </div>
);

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
  const [timeSeriesVisible, setTimeSeriesVisible] = useState(false);
  const handleTimeSeriesVisible = useCallback(() => {
    setTimeSeriesVisible(true);
  }, []);

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
    loadCommLogInfo,
    applyCommLogInfoSnapshot,
    healthPolling,
    statsPolling,
    pollingPausedByVisibility,
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

  const {
    config: spotConfig,
    imageUrl: spotImageUrl,
    imageError: spotImageError,
    imageLoading: spotImageLoading,
    lastSuccessAt: spotLastSuccessAt,
    diagnostics: spotDiagnostics,
    focusBusy,
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
    settingsLeaderState,
    settingsPollingPausedByVisibility,
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

  const hasTimeSeriesWidget = useMemo(() => {
    return hasLayoutTimeSeriesWidget(layoutSnapshot?.layout ?? null);
  }, [layoutSnapshot?.layout]);

  useEffect(() => {
    if (!hasTimeSeriesWidget) {
      setTimeSeriesVisible(false);
    }
  }, [hasTimeSeriesWidget]);

  const {
    data,
    connected,
    lastDataAt,
    latencyMs,
    pollingDegraded,
    pollingIntervalMs,
    pollingFailureCount,
    timeSeriesAllFrame,
    getSeriesStats,
  } = useMetricsViewModel({
    seriesPaused,
    seriesWindowMin,
    showThresholds,
    thresholdConfig,
    timeSeriesFrameActive: settingsOpen || (hasTimeSeriesWidget && (layoutEditing || timeSeriesVisible))
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
  const statusRef = useRef<string | null>(null);
  const spotAlertRef = useRef(false);
  const cameraStatusRef = useRef<string | null>(null);
  const cameraStatusTimerRef = useRef<NodeJS.Timeout | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
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
  // --- Data Fetching Hooks (Same as before) ---

  useEffect(() => {
    if (!layoutEditing && !menuOpen) {
      return;
    }
    fetchLayoutSlots();
  }, [layoutEditing, menuOpen, fetchLayoutSlots]);

  /* Polling and timeSeriesAllFrame computation moved to useMetricsViewModel */

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

  // --- 4. Layout Handlers ---
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
    captureCurrentLayout: () => layoutRef.current,
  });

  const handleSaveCurrentLayout = useCallback(async () => {
    await saveLayout();
  }, [saveLayout]);

  const handleReconnect = async () => {
    // Busy check is handled in hook, but UI disabling is via reconnectBusy from hook
    const success = await reconnect();
    if (success) {
      await modal.alert('Reconnect requested. Check status badge.');
    } else {
      await modal.alert('Reconnect failed.');
    }
  };

  const openSettingsAfterBootstrap = useCallback(async () => {
    await loadSettings();
    setSettingsOpen(true);
    setMenuOpen(false);
    void fetchCentralStatus();
  }, [fetchCentralStatus, loadSettings, setSettingsOpen]);

  const getSettingsPasswordRequired = useCallback(async (): Promise<boolean> => {
    const snapshot = await configService.getConfig();
    return Boolean(snapshot.values.settings.password_set);
  }, []);

  const handleOpenSettings = useCallback(async () => {
    let passwordRequired: boolean;
    try {
      passwordRequired = await getSettingsPasswordRequired();
    } catch (error) {
      console.error('Settings password status check failed', error);
      await modal.alert('\uC124\uC815 \uBE44\uBC00\uBC88\uD638 \uC0C1\uD0DC\uB97C \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.');
      return;
    }
    if (!passwordRequired) {
      await openSettingsAfterBootstrap();
      return;
    }

    const password = await modal.prompt(
      '\uC124\uC815\uC744 \uC5F4\uB824\uBA74 \uAD00\uB9AC\uC790 \uBE44\uBC00\uBC88\uD638\uB97C \uC785\uB825\uD558\uC138\uC694.',
      '',
      { inputType: 'password', title: '\uAD00\uB9AC\uC790 \uBE44\uBC00\uBC88\uD638' }
    );
    
    if (password === null) {
      return;
    }
    
    try {
      const result = await configService.verifyPassword(password);
      if (result.ok) {
        await openSettingsAfterBootstrap();
      }
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || '\uBE44\uBC00\uBC88\uD638\uAC00 \uC62C\uBC14\uB974\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4.';
      await modal.alert(errMsg);
    }
  }, [getSettingsPasswordRequired, modal, openSettingsAfterBootstrap]);



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
      pushNotification('SPOT \uACBD\uACE0', 'SPOT \uC628\uB3C4 \uACBD\uACE0 \uC0C1\uD0DC\uC785\uB2C8\uB2E4.', 'error');
    }
    if (spotAlertRef.current === true && !spotAlertActive) {
      pushNotification('SPOT \uC815\uC0C1', 'SPOT \uC628\uB3C4\uAC00 \uC815\uC0C1 \uBC94\uC704\uB85C \uBCF5\uADC0\uD588\uC2B5\uB2C8\uB2E4.', 'info');
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
      if (type === 'error') {
        pushNotification('\uCE74\uBA54\uB77C \uC624\uB958', 'SPOT \uCE74\uBA54\uB77C ' + (cameraStatus?.title ?? '\uC624\uB958'), 'error');
      } else if (type === 'danger') {
        pushNotification('\uCE74\uBA54\uB77C \uC9C0\uC5F0', 'SPOT \uCE74\uBA54\uB77C ' + (cameraStatus?.title ?? '\uC9C0\uC5F0'), 'warn');
      } else if (type === 'warn') {
        pushNotification('\uCE74\uBA54\uB77C \uC9C0\uC5F0', 'SPOT \uCE74\uBA54\uB77C \uC751\uB2F5\uC774 \uC9C0\uC5F0\uB429\uB2C8\uB2E4.', 'warn');
      } else if (type === 'ok' && cameraStatusRef.current !== 'ok') {
        pushNotification('\uCE74\uBA54\uB77C \uC815\uC0C1', 'SPOT \uCE74\uBA54\uB77C\uAC00 \uC815\uC0C1\uD654\uB418\uC5C8\uC2B5\uB2C8\uB2E4.', 'info');
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

  const dataContextValue = useMemo(() => ({
    data,
    thresholds: thresholdState,
    timeSeriesAllFrame,
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
    seriesWindowMin,
    seriesPaused,
    showThresholds,
    setSeriesWindowMin,
    setSeriesPaused,
    setShowThresholds,
    handleSnapshot,
    snapshotLoading,
    layoutEditing,
    setLayoutEditing,
    intervalSec: Number(settingsForm?.intervalSec ?? '0.2') || 0.2,
  }), [
    data,
    thresholdState,
    timeSeriesAllFrame,
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    spotAlertActive,
    lastDataAt,
    handleSpotImageLoaded,
    handleSpotImageError,
    requestFocus,
    seriesWindowMin,
    seriesPaused,
    showThresholds,
    setSeriesWindowMin,
    setSeriesPaused,
    setShowThresholds,
    handleSnapshot,
    snapshotLoading,
    layoutEditing,
    setLayoutEditing,
    settingsForm?.intervalSec,
  ]);

  const layoutEditContextValue = useMemo(() => ({
    isEditing: layoutEditing,
    deleteWidget: handleRemoveWidget,
    updateWidget: handleUpdateWidget
  }), [layoutEditing, handleRemoveWidget, handleUpdateWidget]);

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
        saveLayout={handleSaveCurrentLayout}
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
      {notificationsOpen ? (
        <React.Suspense fallback={null}>
          <NotificationDrawer
            notifications={notifications}
            notificationsOpen={notificationsOpen}
            setNotificationsOpen={setNotificationsOpen}
            clearNotifications={clearNotifications}
          />
        </React.Suspense>
      ) : null}
      {settingsOpen ? (
        <React.Suspense fallback={<LazyModalFallback title="설정" />}>
          <SettingsModalContainer
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
        configWritable={configWritable}
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
        connectionTest={connectionTest}
        runConnectionTest={runConnectionTest}
        pathHealth={pathHealth}
        checkPathsHealth={checkPathsHealth}
        createPath={createPath}
        setPathHealth={setPathHealth}
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
        getSeriesStats={getSeriesStats}
        timeSeriesAllFrame={timeSeriesAllFrame}
        layoutSnapshot={layoutSnapshot}
        spotConfig={spotConfig}
        spotImageUrl={spotImageUrl}
        spotImageLoading={spotImageLoading}
        spotLastSuccessAt={spotLastSuccessAt}
        spotDiagnostics={spotDiagnostics}
        commLogInfo={commLogInfo}
        loadCommLogInfo={loadCommLogInfo}
        applyCommLogInfoSnapshot={applyCommLogInfoSnapshot}
        openCommLogPath={openCommLogPath}
        openCommLogFile={openCommLogFile}
        frontErrors={frontErrors}
        clearFrontErrors={clearFrontErrors}
        thresholdState={thresholdState}
        settingsLeaderState={settingsLeaderState}
        settingsPollingPausedByVisibility={settingsPollingPausedByVisibility}
        pollingPausedByVisibility={pollingPausedByVisibility}
        setSettingsError={setSettingsError}
        pushNotification={pushNotification}
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
        </React.Suspense>
      ) : null}
      <div className="scene-container" style={{ flexGrow: 1 }}>
        {/* The ReactWidget will be rendered *inside* this provider hierarchy. */}
        <DataContext.Provider value={dataContextValue}>
          <UIContext.Provider value={uiContextValue}>
            <SnapshotContext.Provider value={snapshotContextValue}>
              <LayoutEditContext.Provider value={layoutEditContextValue}>
                <React.Suspense fallback={<div className="widget-loading">Loading...</div>}>
                  {layoutEditing ? (
                    <DashboardSceneSurface
                      layoutSnapshotLayout={layoutSnapshot?.layout ?? null}
                      layoutEditing={layoutEditing}
                      layoutRef={layoutRef}
                      onSpotImageLoaded={handleSpotImageLoaded}
                      onSpotImageError={handleSpotImageError}
                      requestFocus={requestFocus}
                      focusBusy={focusBusy}
                    />
                  ) : (
                    <NativeDashboardSurface
                      layoutSnapshotLayout={layoutSnapshot?.layout ?? null}
                      layoutRef={layoutRef}
                      onSpotImageLoaded={handleSpotImageLoaded}
                      onSpotImageError={handleSpotImageError}
                      requestFocus={requestFocus}
                      focusBusy={focusBusy}
                      onTimeSeriesVisible={handleTimeSeriesVisible}
                    />
                  )}
                </React.Suspense>
              </LayoutEditContext.Provider>
            </SnapshotContext.Provider>
          </UIContext.Provider>
        </DataContext.Provider>
        <AIChatbotLauncher />
        <footer className="app-footer">
          Copyright 癲?HOIHOU. All Rights Reserved. v{packageJson.version}
        </footer>
      </div>
    </div>
  );
}

export default App;
