import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const mockValues = vi.hoisted(() => {
  const thresholdState = {
    masterOn: false,
    entries: {
      speed: { enabled: false, value: null },
      press: { enabled: false, value: null },
      spot: { enabled: false, value: null },
      temp_f: { enabled: false, value: null },
      temp_b: { enabled: false, value: null },
      billet: { enabled: false, value: null },
      billet_temp: { enabled: false, value: null },
      at_temp: { enabled: false, value: null },
      at_pre: { enabled: false, value: null },
      count: { enabled: false, value: null },
      endpos: { enabled: false, value: null },
    },
  };

  const asyncNull = async (): Promise<null> => null;
  const asyncVoid = async (): Promise<void> => undefined;
  const asyncTrue = async (): Promise<boolean> => true;
  const syncVoid = (): void => undefined;

  return {
    asyncNull,
    asyncTrue,
    asyncVoid,
    syncVoid,
    thresholdState,
  };
});

vi.mock('./domains/Layout/components/DashboardHeader/DashboardHeader', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');

  return {
    DashboardHeader: (): JSX.Element => ReactModule.createElement('header', { 'data-testid': 'dashboard-header' }),
  };
});

vi.mock('./AI/components/AIChatbotLauncher', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');

  return {
    AIChatbotLauncher: (): JSX.Element => ReactModule.createElement('div', { 'data-testid': 'ai-chatbot-launcher' }),
  };
});

vi.mock('./scenes/DashboardSceneSurface', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');

  return {
    DashboardSceneSurface: (): JSX.Element => ReactModule.createElement('div', { 'data-testid': 'dashboard-scene' }),
  };
});

vi.mock('./scenes/NativeDashboardSurface', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');
  const { UIContext } = await vi.importActual<typeof import('./domains/FacilityData/context/UIContext')>(
    './domains/FacilityData/context/UIContext'
  );

  return {
    NativeDashboardSurface: (): JSX.Element => {
      const { seriesWindowMin } = ReactModule.useContext(UIContext);

      return ReactModule.createElement('div', { 'data-testid': 'series-window-min' }, String(seriesWindowMin));
    },
  };
});

vi.mock('./domains/Configuration/components/SettingsModal/SettingsModalContainer', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');

  return {
    SettingsModalContainer: (): JSX.Element => ReactModule.createElement('div', { 'data-testid': 'settings-modal' }),
  };
});

vi.mock('./shared/hooks/useThemeContext', () => ({
  useTheme: () => ({
    mode: 'dark',
    activeCycle: 'night',
    setMode: mockValues.syncVoid,
  }),
}));

vi.mock('./shared/hooks/useGlobalModalContext', () => ({
  useModal: () => ({
    alert: mockValues.asyncVoid,
    confirm: mockValues.asyncTrue,
    prompt: mockValues.asyncNull,
  }),
}));

vi.mock('./domains/Configuration/hooks/useViewportScale', () => ({
  applyRowHeightToCSS: mockValues.syncVoid,
  useViewportScale: () => ({
    rowHeight: 48,
    scaleFactor: 1,
    aspectRatio: 1,
  }),
}));

vi.mock('./domains/Observability/hooks/useSystemViewModel', () => ({
  useSystemViewModel: () => ({
    health: null,
    stats: null,
    observabilityErrors: null,
    frontErrors: [],
    pathHealth: {},
    connectionTest: null,
    reconnectBusy: false,
    pathCheckBusy: false,
    observabilityLoading: false,
    healthPolling: { degraded: false, intervalMs: 0, failureCount: 0 },
    statsPolling: { degraded: false, intervalMs: 0, failureCount: 0 },
    dashboardLeaderState: null,
    pollingPausedByVisibility: false,
    fetchHealth: mockValues.asyncNull,
    fetchStats: mockValues.asyncNull,
    loadObservabilityErrors: mockValues.asyncVoid,
    clearObservabilityErrors: mockValues.asyncVoid,
    reconnect: mockValues.asyncTrue,
    runConnectionTest: mockValues.asyncVoid,
    checkPathHealth: mockValues.asyncVoid,
    checkPathsHealth: async (): Promise<Record<string, unknown>> => ({}),
    createPath: mockValues.asyncTrue,
    browseFolder: mockValues.asyncNull,
    setPathHealth: mockValues.syncVoid,
    setPathCheckBusy: mockValues.syncVoid,
    lastExportPath: null,
    fetchLatestExportPath: mockValues.asyncVoid,
    exportObservability: mockValues.asyncNull,
    openExportFolder: mockValues.asyncVoid,
    openExportFile: mockValues.asyncVoid,
    commLogInfo: { path: null },
    loadCommLogInfo: mockValues.asyncNull,
    applyCommLogInfoSnapshot: mockValues.syncVoid,
    fetchCommLogInfo: mockValues.asyncVoid,
    openCommLogPath: mockValues.asyncVoid,
    openCommLogFile: mockValues.asyncVoid,
    saveSnapshot: mockValues.asyncVoid,
  }),
}));

vi.mock('./domains/FacilityData/hooks/useSpotViewModel', () => ({
  useSpotViewModel: () => ({
    config: null,
    imageUrl: '',
    imageError: null,
    imageLoading: false,
    lastSuccessAt: null,
    metadata: null,
    diagnostics: {},
    focusBusy: false,
    refreshConfig: mockValues.asyncVoid,
    refreshImage: mockValues.syncVoid,
    controlSpot: mockValues.asyncTrue,
    controlFocus: mockValues.asyncVoid,
    controlActuator: mockValues.asyncVoid,
    handleImageLoad: mockValues.syncVoid,
    handleImageError: mockValues.syncVoid,
  }),
}));

vi.mock('./domains/Configuration/hooks/useConfigViewModel', () => ({
  useConfigViewModel: () => ({
    settingsOpen: false,
    settingsLoading: false,
    settingsError: null,
    settingsInfo: null,
    settingsForm: null,
    settingsBaseline: null,
    settingsRestartRequired: false,
    settingsApplyResult: null,
    settingsPending: null,
    settingsPendingBusy: false,
    settingsConfigPath: null,
    configWritable: null,
    overrideEnabled: false,
    overrideMeta: null,
    centralStatus: null,
    centralSyncBusy: false,
    thresholdConfig: mockValues.thresholdState,
    settingsToast: null,
    hasSettingsChanges: false,
    validationErrors: {},
    hasValidationError: false,
    activeThresholds: mockValues.thresholdState,
    handleExternalRefresh: mockValues.asyncVoid,
    handleExternalIgnore: mockValues.syncVoid,
    handleCentralSync: mockValues.asyncVoid,
    showSettingsToast: mockValues.syncVoid,
    setSettingsOpen: mockValues.syncVoid,
    setSettingsError: mockValues.syncVoid,
    setSettingsInfo: mockValues.syncVoid,
    loadSettings: mockValues.asyncVoid,
    updateSettingsField: mockValues.syncVoid,
    handleSaveSettings: mockValues.asyncTrue,
    handleRestoreDefaults: mockValues.asyncVoid,
    handleRestoreBackup: mockValues.asyncVoid,
    handlePendingApply: mockValues.asyncVoid,
    handlePendingClear: mockValues.asyncVoid,
    handleMasterToggle: mockValues.syncVoid,
    handleOverrideToggle: mockValues.asyncVoid,
    fetchCentralStatus: mockValues.asyncVoid,
    externalConfigPending: null,
    externalConfigPendingAt: null,
    overrideBusy: false,
    isSettingsFieldDirty: (): boolean => false,
  }),
}));

vi.mock('./domains/Configuration/hooks/useLayoutViewModel', () => ({
  useLayoutViewModel: () => ({
    layoutSnapshot: null,
    layoutSlots: [],
    layoutActiveId: null,
    layoutEditing: false,
    layoutLoadError: null,
    layoutSaveMessage: null,
    layoutSaveError: null,
    storageMode: 'local',
    setLayoutEditing: mockValues.syncVoid,
    setStorageMode: mockValues.syncVoid,
    loadLayoutSnapshot: mockValues.asyncVoid,
    handleSaveLayout: mockValues.asyncVoid,
    handleRestoreLayout: mockValues.asyncVoid,
    handleDeleteLayout: mockValues.asyncVoid,
    applyPreset: mockValues.syncVoid,
    updateWidget: mockValues.syncVoid,
    deleteWidget: mockValues.syncVoid,
    addWidget: mockValues.syncVoid,
    fetchLayoutSlots: mockValues.asyncVoid,
    readLegacyLayoutSnapshot: (): null => null,
  }),
}));

vi.mock('./domains/FacilityData/hooks/useMetricsViewModel', () => ({
  useMetricsViewModel: () => ({
    data: null,
    connected: false,
    lastDataAt: null,
    latencyMs: null,
    pollingDegraded: false,
    pollingIntervalMs: 0,
    pollingFailureCount: 0,
    dashboardLeaderState: null,
    pollingPausedByVisibility: false,
    timeSeriesAllFrame: null,
    getSeriesSamples: (): [] => [],
    getSeriesStats: () => ({ count: 0, windowMs: 0, maxPoints: null }),
  }),
}));

describe('App localStorage state', () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it.each(['999', 'NaN'])('normalizes invalid seriesWindowMin storage value %s to 30', async (savedValue: string) => {
    window.localStorage.setItem('seriesWindowMin', savedValue);

    render(<App />);

    expect(await screen.findByTestId('series-window-min')).toHaveTextContent('30');
  });
});
