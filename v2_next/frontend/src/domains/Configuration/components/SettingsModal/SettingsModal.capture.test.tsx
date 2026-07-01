import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  CentralStatus,
  CommLogInfo,
  SettingsFormState,
  SpotPollingDiagnostics,
  ThresholdKey,
  ThresholdState,
} from '../../../../shared/types';
import { SettingsModal, type SettingsModalProps } from './SettingsModal';

const thresholdKeys: ThresholdKey[] = [
  'speed',
  'press',
  'spot',
  'temp_f',
  'temp_b',
  'billet',
  'billet_temp',
  'at_temp',
  'at_pre',
  'count',
  'endpos',
];

const buildThresholdState = (): ThresholdState => ({
  masterOn: false,
  entries: Object.fromEntries(
    thresholdKeys.map((key) => [key, { enabled: false, value: null }])
  ) as ThresholdState['entries'],
});

const buildSettingsForm = (overrides: Partial<SettingsFormState> = {}): SettingsFormState => ({
  extruderIp: '192.168.10.10',
  extruderPort: '12289',
  lsIp: '192.168.10.220',
  lsPort: '2004',
  spotIp: '10.1.10.50',
  spotRefreshInterval: '1',
  spotActuatorStep: '5',
  spotImageCaptureEnabled: true,
  spotImageCaptureMode: 'event',
  spotImageCapturePath: 'spot_images\\ui_capture',
  spotImageCaptureMinIntervalSec: '0',
  spotImageCaptureMaxBytes: '2000000',
  spotImageCaptureRetentionDays: '5',
  spotImageCaptureLinkToObservation: true,
  thresholdMasterOn: false,
  thresholdSpeedEnabled: false,
  thresholdSpeedValue: '',
  thresholdPressEnabled: false,
  thresholdPressValue: '',
  thresholdSpotEnabled: false,
  thresholdSpotValue: '',
  thresholdTempFEnabled: false,
  thresholdTempFValue: '',
  thresholdTempBEnabled: false,
  thresholdTempBValue: '',
  thresholdBilletEnabled: false,
  thresholdBilletValue: '',
  thresholdBilletTempEnabled: false,
  thresholdBilletTempValue: '',
  thresholdAtTempEnabled: false,
  thresholdAtTempValue: '',
  thresholdAtPreEnabled: false,
  thresholdAtPreValue: '',
  thresholdCountEnabled: false,
  thresholdCountValue: '',
  thresholdEndPosEnabled: false,
  thresholdEndPosValue: '',
  logPath: 'C:\\SmartFactoryLogger\\logs',
  snapshotPath: 'C:\\SmartFactoryLogger\\snapshots',
  autoSave: false,
  intervalSec: '0.2',
  operatorMetadataDowntimeResetHours: '8',
  statusWarnMs: '5000',
  statusOfflineMs: '15000',
  password: '',
  passwordSet: true,
  ...overrides,
});

const noop = () => undefined;
const asyncNoop = async () => undefined;
const asyncTrue = async () => true;

const centralStatus: CentralStatus = {
  configured: false,
  running: false,
  server: null,
  device_id: null,
  backoff_sec: 0,
  last_result: {
    status: 'idle',
    message: '',
    version: null,
    at: null,
  },
};

const spotDiagnostics: SpotPollingDiagnostics = {
  in_flight: false,
  refresh_interval_ms: null,
  fetch_count: 0,
  error_count: 0,
  last_fetch_started_at: null,
  last_fetch_completed_at: null,
  last_fetch_latency_ms: null,
  next_fetch_scheduled_at: null,
  last_fetch_reason: null,
};

const commLogInfo: CommLogInfo = {
  path: null,
};

const buildModalProps = (overrides: Partial<SettingsModalProps> = {}): SettingsModalProps => {
  const settingsForm = buildSettingsForm();

  return {
    settingsOpen: true,
    setSettingsOpen: vi.fn(),
    settingsLoading: false,
    settingsError: null,
    settingsInfo: null,
    settingsForm,
    settingsBaseline: settingsForm,
    settingsConfigPath: 'C:\\Users\\user\\AppData\\Roaming\\SmartFactoryLogger\\config.ini',
    settingsRestartRequired: false,
    settingsApplyResult: null,
    settingsPending: null,
    settingsPendingBusy: false,
    settingsToast: null,
    hasSettingsChanges: false,
    validationErrors: {},
    hasValidationError: false,
    configReadOnly: false,
    overrideEnabled: true,
    overrideMeta: { version: 'test', last_sync: null, source: 'local', override_enabled: true },
    overrideBusy: false,
    centralStatus,
    centralSyncBusy: false,
    externalConfigPending: null,
    externalConfigPendingAt: null,
    updateSettingsField: vi.fn(),
    handleSaveSettings: vi.fn(asyncTrue),
    handleRestoreDefaults: vi.fn(),
    handleRestoreBackup: vi.fn(),
    handleOverrideToggle: vi.fn(),
    handleMasterToggle: vi.fn(),
    handlePendingApply: vi.fn(),
    handlePendingClear: vi.fn(),
    handleExternalRefresh: vi.fn(),
    handleExternalIgnore: vi.fn(),
    handleCentralSync: vi.fn(),
    isSettingsFieldDirty: () => false,
    settingsDirtyCount: 0,
    settingsSectionFieldMap: {},
    settingsSectionHasChanges: {},
    buildSettingsSummaryCards: () => [],
    buildSettingsChangeSummary: () => [],
    applyDetails: { applied: [], pending: [] },
    settingsSections: [{ id: 'settings-spot', label: 'SPOT 카메라' }],
    activeSettingsSection: 'settings-spot',
    scrollToSettingsSection: vi.fn(),
    registerSettingsSection: () => noop,
    settingsScrollRef: React.createRef<HTMLDivElement>(),
    connectionTest: {},
    connectionTestBusy: {},
    connectionTestTargets: [],
    handleConnectionTest: vi.fn(asyncNoop),
    pathHealth: {},
    pathCheckBusy: false,
    hasPathError: false,
    hasPathWarn: false,
    logPathFieldState: 'ok',
    snapshotPathFieldState: 'ok',
    runPathHealthCheck: vi.fn(),
    handleCreatePath: vi.fn(),
    browseFolder: vi.fn(async () => null),
    health: null,
    stats: null,
    observabilityErrors: null,
    observabilityLoading: false,
    loadObservabilityErrors: vi.fn(),
    handleExportObservability: vi.fn(),
    handleOpenObservabilityExportFile: vi.fn(),
    handleOpenObservabilityExportFolder: vi.fn(),
    handleCopyObservabilityExportPath: vi.fn(),
    handleClearObservabilityErrors: vi.fn(),
    lastExportPath: null,
    exportBusy: false,
    backendMemory: null,
    backendMemoryDetails: null,
    frontendMemory: null,
    memorySummaryBusy: false,
    memoryDetailsBusy: false,
    memoryRefreshInFlight: false,
    memoryRefreshIntervalMs: 5000,
    profilerStartBusy: false,
    profilerStopBusy: false,
    memoryExportBusy: false,
    memoryExportPath: null,
    memoryLeader: null,
    memoryActionState: {
      refresh: false,
      snapshot: false,
      profiler_action: null,
      export: false,
    },
    lastExportAt: null,
    lastSummaryAt: null,
    lastDetailsAt: null,
    lastExportMetaAt: null,
    summaryRequestCount: 0,
    detailsRequestCount: 0,
    lastSummaryReason: null,
    handleRefreshMemory: vi.fn(),
    handleStartMemoryProfiler: vi.fn(),
    handleStopMemoryProfiler: vi.fn(),
    handleCaptureMemorySnapshot: vi.fn(),
    handleCaptureMemoryGc: vi.fn(),
    handleExportMemory: vi.fn(),
    handleOpenMemoryExportFile: vi.fn(),
    handleOpenMemoryExportFolder: vi.fn(),
    handleCopyMemoryExportPath: vi.fn(),
    spotConfig: null,
    spotImageUrl: '',
    spotImageLoading: false,
    spotLastSuccessAt: null,
    spotImageMetadata: null,
    spotDiagnostics,
    commLogInfo,
    handleOpenCommLogPath: vi.fn(),
    handleOpenCommLogFile: vi.fn(),
    handleCopyCommLogPath: vi.fn(),
    frontErrors: [],
    clearFrontErrors: vi.fn(),
    currentPassword: '',
    setCurrentPassword: vi.fn(),
    passwordConfirm: '',
    setPasswordConfirm: vi.fn(),
    showCurrentPassword: false,
    setShowCurrentPassword: vi.fn(),
    showNewPassword: false,
    setShowNewPassword: vi.fn(),
    showConfirmPassword: false,
    setShowConfirmPassword: vi.fn(),
    thresholdItems: [],
    thresholdState: buildThresholdState(),
    getCameraStatus: () => null,
    commSnapshot: null,
    commDetail: null,
    commSummaryItems: [],
    statsWindow: undefined,
    windowErrorRate: null,
    hasWindowIssue: false,
    windowP95Text: '--',
    errorQueueSize: null,
    errorQueueText: '--',
    lastErrorAt: null,
    spotImageError: null,
    showSettingsToast: vi.fn(),
    ...overrides,
  } as SettingsModalProps;
};

afterEach(() => {
  cleanup();
});

describe('SettingsModal SPOT image capture UI', () => {
  it('renders evidence image capture settings and forwards operator edits', () => {
    const updateSettingsField = vi.fn();

    render(<SettingsModal {...buildModalProps({ updateSettingsField })} />);

    const capturePanel = screen.getByText('증거 이미지 저장').closest('.settings-spot-capture');
    expect(capturePanel).toBeInTheDocument();

    const capture = within(capturePanel as HTMLElement);
    expect(capture.getByText('Event only / 5d retention')).toBeInTheDocument();
    expect(capture.getByDisplayValue('spot_images\\ui_capture')).toBeInTheDocument();

    fireEvent.change(capture.getByDisplayValue('spot_images\\ui_capture'), {
      target: { value: 'spot_images\\changed' },
    });
    expect(updateSettingsField).toHaveBeenCalledWith('spotImageCapturePath', 'spot_images\\changed');

    fireEvent.click(capture.getAllByRole('button', { name: 'ON' })[0]);
    expect(updateSettingsField).toHaveBeenCalledWith('spotImageCaptureEnabled', false);
    expect(updateSettingsField).toHaveBeenCalledWith('spotImageCaptureMode', 'off');
  });
});
