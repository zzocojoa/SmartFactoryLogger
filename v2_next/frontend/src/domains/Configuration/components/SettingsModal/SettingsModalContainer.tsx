import React, { useCallback, useMemo, useState } from 'react';
import type {
  DashboardLeaderState,
  LayoutSnapshot,
  PathHealthResult,
  PathHealthState,
  SettingsFormState,
  ThresholdItem,
} from '../../../../shared/types';
import { CONFIG_LABELS, LABELS, SPOT_UNIT } from '../../../../shared/constants/uiText';
import { useModal } from '../../../../shared/hooks/useGlobalModalContext';
import { useSettingsFormHandlers } from '../../../../shared/hooks/useSettingsFormHandlers';
import { useMemoryViewModel } from '../../../Observability/hooks/useMemoryViewModel';
import { useCommLogInfoEffects } from '../../../Observability/hooks/useSystemViewModelEffects';
import { useSettingsModalState } from './useSettingsModalState';
import { SettingsModal } from './SettingsModal';
import type { SettingsModalProps } from './SettingsModal';

type ManagedSettingsModalProps =
  | 'configReadOnly'
  | 'settingsDirtyCount'
  | 'settingsSectionFieldMap'
  | 'settingsSectionHasChanges'
  | 'buildSettingsSummaryCards'
  | 'buildSettingsChangeSummary'
  | 'applyDetails'
  | 'settingsSections'
  | 'activeSettingsSection'
  | 'scrollToSettingsSection'
  | 'registerSettingsSection'
  | 'settingsScrollRef'
  | 'connectionTestBusy'
  | 'connectionTestTargets'
  | 'handleConnectionTest'
  | 'pathCheckBusy'
  | 'hasPathError'
  | 'hasPathWarn'
  | 'logPathFieldState'
  | 'snapshotPathFieldState'
  | 'runPathHealthCheck'
  | 'handleCreatePath'
  | 'backendMemory'
  | 'backendMemoryDetails'
  | 'frontendMemory'
  | 'memorySummaryBusy'
  | 'memoryDetailsBusy'
  | 'memoryRefreshInFlight'
  | 'memoryRefreshIntervalMs'
  | 'profilerStartBusy'
  | 'profilerStopBusy'
  | 'memoryExportBusy'
  | 'memoryExportPath'
  | 'memoryLeader'
  | 'memoryActionState'
  | 'lastExportAt'
  | 'lastSummaryAt'
  | 'lastDetailsAt'
  | 'lastExportMetaAt'
  | 'summaryRequestCount'
  | 'detailsRequestCount'
  | 'lastSummaryReason'
  | 'handleRefreshMemory'
  | 'handleStartMemoryProfiler'
  | 'handleStopMemoryProfiler'
  | 'handleCaptureMemorySnapshot'
  | 'handleExportMemory'
  | 'handleOpenMemoryExportFile'
  | 'handleOpenMemoryExportFolder'
  | 'handleCopyMemoryExportPath'
  | 'handleOpenCommLogPath'
  | 'handleOpenCommLogFile'
  | 'handleCopyCommLogPath'
  | 'currentPassword'
  | 'setCurrentPassword'
  | 'passwordConfirm'
  | 'setPasswordConfirm'
  | 'showCurrentPassword'
  | 'setShowCurrentPassword'
  | 'showNewPassword'
  | 'setShowNewPassword'
  | 'showConfirmPassword'
  | 'setShowConfirmPassword'
  | 'thresholdItems';

interface PathHealthResponse {
  results?: Record<string, PathHealthResult>;
}

interface SeriesStatsSnapshot {
  count: number;
  windowMs: number;
  maxPoints: number | null;
}

export interface SettingsModalContainerProps
  extends Omit<SettingsModalProps, ManagedSettingsModalProps> {
  runConnectionTest: (payload: unknown) => Promise<void>;
  checkPathsHealth: (payload: Array<{ key: string; path: string }>) => Promise<PathHealthResponse>;
  createPath: (path: string) => Promise<boolean>;
  setPathHealth: React.Dispatch<React.SetStateAction<PathHealthState>>;
  setSettingsError: (message: string | null) => void;
  configWritable: boolean | null;
  settingsLeaderState: DashboardLeaderState | null | undefined;
  settingsPollingPausedByVisibility: boolean | undefined;
  pollingPausedByVisibility: boolean;
  loadCommLogInfo: () => Promise<SettingsModalProps['commLogInfo'] | null>;
  applyCommLogInfoSnapshot: (next: SettingsModalProps['commLogInfo']) => void;
  getSeriesStats: () => SeriesStatsSnapshot;
  timeSeriesAllFrame: unknown | null;
  layoutSnapshot: LayoutSnapshot | null;
  openCommLogPath: () => Promise<void>;
  openCommLogFile: () => Promise<void>;
  pushNotification: (title: string, message: string, level: 'info' | 'warn' | 'error') => void;
}

const settingsSections: Array<{ id: string; label: string }> = [
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
];

const connectionTestTargets: Array<{ key: 'extruder' | 'ls_plc' | 'spot'; label: string }> = [
  { key: 'extruder', label: CONFIG_LABELS.EXTRUDER },
  { key: 'ls_plc', label: CONFIG_LABELS.LS_PLC },
  { key: 'spot', label: LABELS.SPOT_CAMERA },
];

const thresholdItems: ThresholdItem[] = [
  { key: 'speed', label: LABELS.SPEED, unit: 'mm/s', enableField: 'thresholdSpeedEnabled', valueField: 'thresholdSpeedValue' },
  { key: 'press', label: LABELS.PRESS, unit: 'bar', enableField: 'thresholdPressEnabled', valueField: 'thresholdPressValue' },
  { key: 'spot', label: LABELS.SPOT, unit: SPOT_UNIT, enableField: 'thresholdSpotEnabled', valueField: 'thresholdSpotValue' },
  { key: 'temp_f', label: LABELS.CONTAINER_FRONT, unit: SPOT_UNIT, enableField: 'thresholdTempFEnabled', valueField: 'thresholdTempFValue' },
  { key: 'temp_b', label: LABELS.CONTAINER_BACK, unit: SPOT_UNIT, enableField: 'thresholdTempBEnabled', valueField: 'thresholdTempBValue' },
  { key: 'billet', label: LABELS.BILLET_LEN, unit: 'mm', enableField: 'thresholdBilletEnabled', valueField: 'thresholdBilletValue' },
  { key: 'billet_temp', label: LABELS.BILLET_TEMP, unit: SPOT_UNIT, enableField: 'thresholdBilletTempEnabled', valueField: 'thresholdBilletTempValue' },
  { key: 'at_temp', label: LABELS.ENV_TEMP, unit: SPOT_UNIT, enableField: 'thresholdAtTempEnabled', valueField: 'thresholdAtTempValue' },
  { key: 'at_pre', label: LABELS.ENV_HUMID, unit: '%', enableField: 'thresholdAtPreEnabled', valueField: 'thresholdAtPreValue' },
  { key: 'count', label: LABELS.COUNT, unit: 'ea', enableField: 'thresholdCountEnabled', valueField: 'thresholdCountValue' },
  { key: 'endpos', label: LABELS.END_POS, unit: 'mm', enableField: 'thresholdEndPosEnabled', valueField: 'thresholdEndPosValue' },
];

export const SettingsModalContainer = (props: SettingsModalContainerProps): JSX.Element => {
  const modal = useModal();
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');

  const settingsReady = props.settingsForm !== null;
  const configReadOnly = props.configWritable === false;

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
    settingsForm: props.settingsForm,
    settingsBaseline: props.settingsBaseline,
    settingsApplyResult: props.settingsApplyResult,
    overrideMeta: props.overrideMeta,
    pathHealth: props.pathHealth,
    hasSettingsChanges: props.hasSettingsChanges,
    isSettingsFieldDirty: props.isSettingsFieldDirty,
  });

  const {
    activeSettingsSection,
    settingsScrollRef,
    registerSettingsSection,
    scrollToSettingsSection,
    runPathHealthCheck,
    handleConnectionTest,
    handleCreatePath,
    connectionTestBusy,
    pathCheckBusy,
  } = useSettingsFormHandlers({
    settingsForm: props.settingsForm,
    settingsBaseline: props.settingsBaseline,
    settingsOpen: props.settingsOpen,
    settingsReady,
    validationErrors: props.validationErrors,
    isSettingsFieldDirty: props.isSettingsFieldDirty,
    updateSettingsField: props.updateSettingsField,
    runConnectionTest: props.runConnectionTest,
    checkPathsHealth: props.checkPathsHealth,
    createPath: props.createPath,
    modal,
    setSettingsError: props.setSettingsError,
    setPathHealth: props.setPathHealth,
    pathHealth: props.pathHealth,
  });

  useCommLogInfoEffects({
    enabled: props.settingsOpen && activeSettingsSection === 'settings-observability',
    settingsLeaderMode: props.settingsLeaderState?.mode ?? null,
    settingsPollingPausedByVisibility: props.settingsPollingPausedByVisibility ?? false,
    pollingPausedByVisibility: props.pollingPausedByVisibility,
    loadCommLogInfo: props.loadCommLogInfo,
    applyCommLogInfoSnapshot: props.applyCommLogInfoSnapshot,
  });

  const memory = useMemoryViewModel({
    enabled: props.settingsOpen && activeSettingsSection === 'settings-memory',
    seriesStats: props.getSeriesStats(),
    timeSeriesAllFrame: props.timeSeriesAllFrame,
    layoutSnapshot: props.layoutSnapshot,
    observabilityErrors: props.observabilityErrors,
    frontErrors: props.frontErrors,
    spotImageUrl: props.spotImageUrl,
    spotDiagnostics: props.spotDiagnostics,
    settingsForm: props.settingsForm,
    settingsPending: props.settingsPending,
    externalConfigPending: props.externalConfigPending,
  });

  const handleCopyCommLogPath = useCallback((): void => {
    if (!props.commLogInfo.path) {
      return;
    }
    navigator.clipboard.writeText(props.commLogInfo.path);
    props.pushNotification('경로 복사 완료', '통신 로그 경로를 클립보드에 복사했습니다.', 'info');
  }, [props]);

  const handleOpenCommLogPath = useCallback(async (): Promise<void> => {
    if (!props.commLogInfo.path) {
      return;
    }
    try {
      await props.openCommLogPath();
      props.showSettingsToast('통신 로그 폴더를 열었습니다.', 'ok');
    } catch (error) {
      console.error('Open comm log path failed', error);
      props.showSettingsToast('통신 로그 폴더를 열지 못했습니다.', 'error');
    }
  }, [props]);

  const handleOpenCommLogFile = useCallback(async (): Promise<void> => {
    if (!props.commLogInfo.path) {
      return;
    }
    try {
      await props.openCommLogFile();
      props.showSettingsToast('통신 로그 파일을 열었습니다.', 'ok');
    } catch (error) {
      console.error('Open comm log file failed', error);
      props.showSettingsToast('통신 로그 파일을 열지 못했습니다.', 'error');
    }
  }, [props]);

  const handleRefreshMemory = useCallback(async (): Promise<void> => {
    try {
      await memory.refreshMemory();
      props.showSettingsToast('메모리 정보를 새로고침했습니다.', 'ok');
    } catch (error) {
      console.error('Memory refresh failed', error);
      props.showSettingsToast('메모리 정보를 새로고침하지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleStartMemoryProfiler = useCallback(async (): Promise<void> => {
    try {
      await memory.startMemoryProfiler();
      props.showSettingsToast('메모리 상세 추적을 시작했습니다.', 'ok');
    } catch (error) {
      console.error('Memory profiler start failed', error);
      props.showSettingsToast('메모리 상세 추적을 시작하지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleStopMemoryProfiler = useCallback(async (): Promise<void> => {
    try {
      await memory.stopMemoryProfiler();
      props.showSettingsToast('메모리 상세 추적을 중지했습니다.', 'ok');
    } catch (error) {
      console.error('Memory profiler stop failed', error);
      props.showSettingsToast('메모리 상세 추적을 중지하지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleCaptureMemorySnapshot = useCallback(async (): Promise<void> => {
    try {
      await memory.captureMemorySnapshot();
      props.showSettingsToast('메모리 snapshot을 생성했습니다.', 'ok');
    } catch (error) {
      console.error('Memory snapshot failed', error);
      props.showSettingsToast('메모리 snapshot을 생성하지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleExportMemory = useCallback(async (): Promise<void> => {
    try {
      const path = await memory.exportMemory();
      if (!path) {
        throw new Error('Memory export path missing');
      }
      props.showSettingsToast('메모리 export를 생성했습니다.', 'ok');
    } catch (error) {
      console.error('Memory export failed', error);
      props.showSettingsToast('메모리 export를 생성하지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleOpenMemoryExportFile = useCallback(async (): Promise<void> => {
    try {
      await memory.openMemoryExportFile();
    } catch (error) {
      console.error('Open memory export file failed', error);
      props.showSettingsToast('메모리 export 파일을 열지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleOpenMemoryExportFolder = useCallback(async (): Promise<void> => {
    try {
      await memory.openMemoryExportFolder();
    } catch (error) {
      console.error('Open memory export folder failed', error);
      props.showSettingsToast('메모리 export 폴더를 열지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const handleCopyMemoryExportPath = useCallback(async (): Promise<void> => {
    try {
      await memory.copyMemoryExportPath();
      props.showSettingsToast('메모리 export 경로를 클립보드에 복사했습니다.', 'ok');
    } catch (error) {
      console.error('Copy memory export path failed', error);
      props.showSettingsToast('메모리 export 경로를 복사하지 못했습니다.', 'error');
    }
  }, [memory, props]);

  const forwardedProps = useMemo(
    () => ({
      ...props,
      configReadOnly,
      settingsDirtyCount,
      settingsSectionFieldMap,
      settingsSectionHasChanges,
      buildSettingsSummaryCards,
      buildSettingsChangeSummary,
      applyDetails,
      settingsSections,
      activeSettingsSection,
      scrollToSettingsSection,
      registerSettingsSection,
      settingsScrollRef,
      connectionTestBusy,
      connectionTestTargets,
      handleConnectionTest,
      pathCheckBusy,
      hasPathError,
      hasPathWarn,
      logPathFieldState,
      snapshotPathFieldState,
      runPathHealthCheck,
      handleCreatePath,
      ...memory,
      handleRefreshMemory,
      handleStartMemoryProfiler,
      handleStopMemoryProfiler,
      handleCaptureMemorySnapshot,
      handleExportMemory,
      handleOpenMemoryExportFile,
      handleOpenMemoryExportFolder,
      handleCopyMemoryExportPath,
      handleOpenCommLogPath,
      handleOpenCommLogFile,
      handleCopyCommLogPath,
      currentPassword,
      setCurrentPassword,
      passwordConfirm,
      setPasswordConfirm,
      showCurrentPassword,
      setShowCurrentPassword,
      showNewPassword,
      setShowNewPassword,
      showConfirmPassword,
      setShowConfirmPassword,
      thresholdItems,
    }),
    [
      props,
      configReadOnly,
      settingsDirtyCount,
      settingsSectionFieldMap,
      settingsSectionHasChanges,
      buildSettingsSummaryCards,
      buildSettingsChangeSummary,
      applyDetails,
      activeSettingsSection,
      scrollToSettingsSection,
      registerSettingsSection,
      settingsScrollRef,
      connectionTestBusy,
      handleConnectionTest,
      pathCheckBusy,
      hasPathError,
      hasPathWarn,
      logPathFieldState,
      snapshotPathFieldState,
      runPathHealthCheck,
      handleCreatePath,
      memory,
      handleRefreshMemory,
      handleStartMemoryProfiler,
      handleStopMemoryProfiler,
      handleCaptureMemorySnapshot,
      handleExportMemory,
      handleOpenMemoryExportFile,
      handleOpenMemoryExportFolder,
      handleCopyMemoryExportPath,
      handleOpenCommLogPath,
      handleOpenCommLogFile,
      handleCopyCommLogPath,
      currentPassword,
      passwordConfirm,
      showCurrentPassword,
      showNewPassword,
      showConfirmPassword,
    ]
  );

  return <SettingsModal {...forwardedProps} />;
};
