/**
 * SettingsModal – extracted from App.tsx (Phase 12)
 *
 * Pure presentational component for the full Settings Modal.
 * All state and handlers are passed in via props from App.tsx.
 */
import React, { useEffect, useRef } from 'react';
import type {
  SettingsFormState,
  ConnectionTestResult,
  ConnectionTestState,
  ConnectionTargetKey,
  PathHealthResult,
  PathHealthState,
  HealthSnapshot,
  FrontendMemorySnapshot,
  MemoryActionState,
  MemoryDetailsResponse,
  MemoryTabLeaderState,
  MemoryStateResponse,
  StatsSnapshot,
  SpotConfig,
  SpotPollingDiagnostics,
  ObservabilityErrorItem,
  FrontendErrorEntry,
  CentralStatus,
  CommLogInfo,
  ConfigApplyResult,
  ConfigSnapshot,
  ThresholdKey,
  ThresholdState,
} from '../../../../shared/types';
import type { SpotImageResponseMetadata } from '../../../FacilityData/api/spotService.types';
import { MemorySection } from './MemorySection';
import {
  formatTime,
  formatMetaTime,
  formatAgeSec,
  formatOptionalNumber,
  formatOptionalSeconds,
  formatOptionalText,
  formatTimeFromSec,
} from '../../../../shared/utils/formatters';
import {
  LABELS,
  MESSAGES,
  STATUS,
  CONFIG_LABELS,
} from '../../../../shared/constants/uiText';
import {
  getTestBadge,
  formatTestTime,
  getPathBadge,
  formatPathCheckTime,
  formatPathMessage,
  getCentralBadge,
  formatCentralTime,
} from './settingsModalHelpers';
import type { SaveSettingsOptions } from '../../hooks/useConfigViewModel.types';
import packageJson from '../../../../../package.json';

/* ─── Props ────────────────────────────────────────────────────── */

export interface SettingsModalProps {
  // Open/close
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;

  // Config state
  settingsLoading: boolean;
  settingsError: string | null;
  settingsInfo: string | null;
  settingsForm: SettingsFormState | null;
  settingsBaseline: SettingsFormState | null;
  settingsConfigPath: string | null;
  settingsRestartRequired: boolean;
  settingsApplyResult: ConfigApplyResult | null;
  settingsPending: { path?: string; created_at?: string; source?: string; reason?: string } | null | undefined;
  settingsPendingBusy: boolean;
  settingsToast: { message: string; level: string } | null;
  hasSettingsChanges: boolean;
  validationErrors: Record<string, string>;
  hasValidationError: boolean;
  configReadOnly: boolean;
  overrideEnabled: boolean;
  overrideMeta: { version?: string | null; last_sync?: string | null; source?: string | null; override_enabled?: boolean } | null | undefined;
  overrideBusy: boolean;
  centralStatus: CentralStatus | null;
  centralSyncBusy: boolean;
  externalConfigPending: ConfigSnapshot | null;
  externalConfigPendingAt: number | null;

  // Config actions
  updateSettingsField: (field: keyof SettingsFormState, value: any) => void;
  handleSaveSettings: (options?: SaveSettingsOptions) => Promise<boolean>;
  handleRestoreDefaults: () => void;
  handleRestoreBackup: () => void;
  handleOverrideToggle: () => void;
  handleMasterToggle: (checked: boolean) => void;
  handlePendingApply: () => void;
  handlePendingClear: () => void;
  handleExternalRefresh: () => void;
  handleExternalIgnore: () => void;
  handleCentralSync: () => void;
  isSettingsFieldDirty: (field: keyof SettingsFormState) => boolean;

  // Computed settings state (from useSettingsModalState)
  settingsDirtyCount: number;
  settingsSectionFieldMap: Record<string, Array<keyof SettingsFormState>>;
  settingsSectionHasChanges: Record<string, boolean>;
  buildSettingsSummaryCards: () => Array<{ title: string; items: string[] }>;
  buildSettingsChangeSummary: () => string[];
  applyDetails: { applied: string[]; pending: string[] };

  // Settings navigation
  settingsSections: Array<{ id: string; label: string }>;
  activeSettingsSection: string;
  scrollToSettingsSection: (id: string) => void;
  registerSettingsSection: (id: string) => (el: HTMLDivElement | null) => void;
  settingsScrollRef: React.RefObject<HTMLDivElement | null> | React.RefObject<HTMLDivElement>;

  // Connection test
  connectionTest: ConnectionTestState;
  connectionTestBusy: Record<string, boolean>;
  connectionTestTargets: Array<{ key: ConnectionTargetKey; label: string }>;
  handleConnectionTest: (target: ConnectionTargetKey) => Promise<void>;

  // Path health
  pathHealth: PathHealthState;
  pathCheckBusy: boolean;
  hasPathError: boolean;
  hasPathWarn: boolean;
  logPathFieldState: string;
  snapshotPathFieldState: string;
  runPathHealthCheck: (targets?: Array<{ key: 'log' | 'snapshot'; path: string }>) => void;
  handleCreatePath: (pathField: string) => void;
  browseFolder: (params?: { initial_dir?: string; title?: string }) => Promise<string | null>;

  // Observability
  health: HealthSnapshot | null;
  stats: StatsSnapshot | null;
  observabilityErrors: any;
  observabilityLoading: boolean;
  loadObservabilityErrors: () => void;
  handleExportObservability: () => void;
  handleOpenObservabilityExportFile: () => void;
  handleOpenObservabilityExportFolder: () => void;
  handleCopyObservabilityExportPath: () => void;
  handleClearObservabilityErrors: () => void;
  lastExportPath: string | null;
  exportBusy: boolean;
  backendMemory: MemoryStateResponse | null;
  backendMemoryDetails: MemoryDetailsResponse | null;
  frontendMemory: FrontendMemorySnapshot | null;
  memorySummaryBusy: boolean;
  memoryDetailsBusy: boolean;
  memoryRefreshInFlight: boolean;
  memoryRefreshIntervalMs: number;
  profilerStartBusy: boolean;
  profilerStopBusy: boolean;
  memoryExportBusy: boolean;
  memoryExportPath: string | null;
  memoryLeader: MemoryTabLeaderState | null;
  memoryActionState: MemoryActionState;
  lastExportAt: number | null;
  lastSummaryAt: number | null;
  lastDetailsAt: number | null;
  lastExportMetaAt: number | null;
  summaryRequestCount: number;
  detailsRequestCount: number;
  lastSummaryReason: string | null;
  handleRefreshMemory: () => void;
  handleStartMemoryProfiler: () => void;
  handleStopMemoryProfiler: () => void;
  handleCaptureMemorySnapshot: () => void;
  handleExportMemory: () => void;
  handleOpenMemoryExportFile: () => void;
  handleOpenMemoryExportFolder: () => void;
  handleCopyMemoryExportPath: () => void;

  // SPOT
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotLastSuccessAt: number | null;
  spotImageMetadata: SpotImageResponseMetadata | null;
  spotDiagnostics: SpotPollingDiagnostics;

  // Comm log
  commLogInfo: CommLogInfo;
  handleOpenCommLogPath: () => void;
  handleOpenCommLogFile: () => void;
  handleCopyCommLogPath: () => void;

  // Frontend errors
  frontErrors: FrontendErrorEntry[];
  clearFrontErrors: () => void;

  // Password UI state
  currentPassword: string;
  setCurrentPassword: (v: string) => void;
  passwordConfirm: string;
  setPasswordConfirm: (v: string) => void;
  showCurrentPassword: boolean;
  setShowCurrentPassword: (v: boolean) => void;
  showNewPassword: boolean;
  setShowNewPassword: (v: boolean) => void;
  showConfirmPassword: boolean;
  setShowConfirmPassword: (v: boolean) => void;

  // Thresholds
  thresholdItems: Array<{ key: ThresholdKey; label: string; unit: string; enableField: keyof SettingsFormState; valueField: keyof SettingsFormState }>;
  thresholdState: ThresholdState;

  // Misc helpers used in JSX
  getCameraStatus: (params: any) => any;
  nowTick: number;

  // Computed render-time values passed from App.tsx
  commSnapshot: any;
  commDetail: any;
  commSummaryItems: any[];
  statsWindow: any;
  windowErrorRate: number | null;
  hasWindowIssue: boolean;
  windowP95Text: string;
  errorQueueSize: number | null;
  errorQueueText: string;
  lastErrorAt: number | null;
  spotImageError: string | null;
  showSettingsToast: (msg: string, level: 'ok' | 'warn' | 'error') => void;
}

/* ─── Component ────────────────────────────────────────────────── */

export function SettingsModal(props: SettingsModalProps) {
  const {
    settingsOpen,
    setSettingsOpen,
    settingsLoading,
    settingsError,
    settingsInfo,
    settingsForm,
    settingsBaseline,
    settingsConfigPath,
    settingsRestartRequired,
    settingsApplyResult,
    settingsPending,
    settingsPendingBusy,
    settingsToast,
    hasSettingsChanges,
    validationErrors,
    hasValidationError,
    configReadOnly,
    overrideEnabled,
    overrideMeta,
    overrideBusy,
    centralStatus,
    centralSyncBusy,
    externalConfigPending,
    externalConfigPendingAt,
    updateSettingsField,
    handleSaveSettings,
    handleRestoreDefaults,
    handleRestoreBackup,
    handleOverrideToggle,
    handleMasterToggle,
    handlePendingApply,
    handlePendingClear,
    handleExternalRefresh,
    handleExternalIgnore,
    handleCentralSync,
    isSettingsFieldDirty,
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
    connectionTest,
    connectionTestBusy,
    connectionTestTargets,
    handleConnectionTest,
    pathHealth,
    pathCheckBusy,
    hasPathError,
    hasPathWarn,
    logPathFieldState,
    snapshotPathFieldState,
    runPathHealthCheck,
    handleCreatePath,
    browseFolder,
    health,
    stats,
    observabilityErrors,
    observabilityLoading,
    loadObservabilityErrors,
    handleExportObservability,
    handleOpenObservabilityExportFile,
    handleOpenObservabilityExportFolder,
    handleCopyObservabilityExportPath,
    handleClearObservabilityErrors,
    lastExportPath,
    exportBusy,
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
    handleRefreshMemory,
    handleStartMemoryProfiler,
    handleStopMemoryProfiler,
    handleCaptureMemorySnapshot,
    handleExportMemory,
    handleOpenMemoryExportFile,
    handleOpenMemoryExportFolder,
    handleCopyMemoryExportPath,
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotLastSuccessAt,
    spotImageMetadata,
    spotDiagnostics,
    commLogInfo,
    handleOpenCommLogPath,
    handleOpenCommLogFile,
    handleCopyCommLogPath,
    frontErrors,
    clearFrontErrors,
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
    thresholdState,
    getCameraStatus,
    nowTick,
    commSnapshot,
    commDetail,
    commSummaryItems,
    statsWindow,
    windowErrorRate,
    hasWindowIssue,
    windowP95Text,
    errorQueueSize,
    errorQueueText,
    lastErrorAt,
    spotImageError,
    showSettingsToast,
  } = props;

  useEffect(() => {
    if (!settingsOpen) {
      setCurrentPassword('');
      setPasswordConfirm('');
      setShowCurrentPassword(false);
      setShowNewPassword(false);
      setShowConfirmPassword(false);
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [settingsOpen]);

  useEffect(() => {
    if (!settingsForm || settingsForm.password.trim().length > 0) {
      return;
    }
    setPasswordConfirm('');
  }, [settingsForm, setPasswordConfirm]);

  if (!settingsOpen) return null;

  const spotPollingStats = stats?.polling?.paths?.['/api/spot/proxy_image'];
  const spotPollingClientText = spotPollingStats?.top_clients?.length
    ? spotPollingStats.top_clients.map((item) => `${item.client} ${item.count}`).join(', ')
    : '--';
  const nextPassword = settingsForm?.password.trim() ?? '';
  const trimmedCurrentPassword = currentPassword.trim();
  const trimmedPasswordConfirm = passwordConfirm.trim();
  const hasPasswordChange = nextPassword.length > 0;
  const requiresCurrentPassword = Boolean(settingsForm?.passwordSet && hasPasswordChange);
  const hasPasswordConfirmMismatch =
    hasPasswordChange && trimmedPasswordConfirm !== nextPassword;
  const isCurrentPasswordMissing =
    requiresCurrentPassword && trimmedCurrentPassword.length === 0;
  const isSecuritySaveBlocked = hasPasswordConfirmMismatch || isCurrentPasswordMissing;
  const saveDisabled =
    settingsLoading ||
    pathCheckBusy ||
    hasPathError ||
    hasValidationError ||
    configReadOnly ||
    (!overrideEnabled && hasSettingsChanges) ||
    isSecuritySaveBlocked;
  const footerNoteText = configReadOnly
    ? '?쎄린 ?꾩슜?낅땲??'
    : hasValidationError
      ? '?낅젰媛믪쓣 ?뺤씤?섏꽭??'
      : hasPasswordConfirmMismatch
        ? '비밀번호 확인이 일치해야 저장할 수 있습니다.'
        : isCurrentPasswordMissing
          ? '현재 비밀번호를 검증해야 저장할 수 있습니다.'
          : !overrideEnabled && hasSettingsChanges
            ? '??ν븯?ㅻ㈃ ?ㅻ쾭?쇱씠?쒕? 耳쒖꽭??'
            : '蹂寃??ы빆? ??????곸슜?⑸땲??';

  const securityFooterNoteText = configReadOnly
    ? '읽기 전용입니다.'
    : hasValidationError
      ? '입력값을 확인하세요.'
      : hasPasswordConfirmMismatch
        ? '비밀번호 확인이 일치해야 저장할 수 있습니다.'
        : isCurrentPasswordMissing
          ? '현재 비밀번호를 입력해야 저장할 수 있습니다.'
          : !overrideEnabled && hasSettingsChanges
            ? '저장하려면 오버라이드를 켜세요.'
            : hasPasswordChange
              ? settingsForm?.passwordSet
                ? '비밀번호 변경은 저장 후 적용됩니다.'
                : '비밀번호 설정은 저장 후 적용됩니다.'
              : '변경 사항은 저장 후 적용됩니다.';
  const securityStatusLabel = settingsForm?.passwordSet ? '설정됨' : '미설정';
  const securityIntroText = settingsForm?.passwordSet
    ? '현재 비밀번호를 확인한 뒤 새 비밀번호를 저장합니다.'
    : '설정창 접근에 사용할 비밀번호를 먼저 등록하세요.';
  const newPasswordLabel = settingsForm?.passwordSet ? '새 비밀번호' : '설정 비밀번호';
  const newPasswordPlaceholder = settingsForm?.passwordSet ? '새 비밀번호 입력' : '비밀번호 입력';
  const newPasswordHelpText = settingsForm?.passwordSet
    ? '새 비밀번호를 입력하지 않으면 기존 비밀번호를 유지합니다.'
    : '설정창 접근에 사용할 비밀번호를 등록합니다.';
  const confirmPasswordPlaceholder = settingsForm?.passwordSet
    ? '새 비밀번호 다시 입력'
    : '비밀번호 다시 입력';

  const handleSecuritySave = async () => {
    const didSave = await handleSaveSettings({
      security: {
        currentPassword,
        passwordConfirm,
      },
    });

    if (!didSave) {
      return;
    }

    setCurrentPassword('');
    setPasswordConfirm('');
    setShowCurrentPassword(false);
    setShowNewPassword(false);
    setShowConfirmPassword(false);
  };

  return (
        <div
          className="settings-backdrop"
          onClick={() => setSettingsOpen(false)}
          onWheel={(event) => event.preventDefault()}
          onTouchMove={(event) => event.preventDefault()}
        >
          <div
            className="settings-modal"
            onClick={(event) => event.stopPropagation()}
            onWheel={(event) => event.stopPropagation()}
            onTouchMove={(event) => event.stopPropagation()}
          >
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
                <div className="settings-content" ref={settingsScrollRef as React.RefObject<HTMLDivElement>}>
                  <div className="settings-form">
                    {/* Summary Section */}
                    <div
                      className="settings-section settings-summary"
                      id="settings-summary"
                      ref={registerSettingsSection('settings-summary')}
                    >
                      <div className="settings-section-title">{LABELS.SUMMARY_INFO}</div>
                      <div className="settings-summary-grid">
                        {buildSettingsSummaryCards().map((card, index) => {
                            const isWide = index < 2;
                            return (
                              <div
                                key={`settings-summary-card-${index}`}
                                className={`settings-summary-card ${isWide ? 'wide' : ''}`}
                              >
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
                        <span>설정 버전: {overrideMeta?.version ?? '--'}</span>
                        <span>최근 동기화: {formatMetaTime(overrideMeta?.last_sync)}</span>
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
                          <div className="settings-test-message">
                            HTTP 4xx {statsWindow?.http_4xx_count ?? '--'} / 5xx {statsWindow?.http_5xx_count ?? '--'} | 누적 4xx {stats?.total_http_4xx_count ?? '--'} / 누적 5xx {stats?.total_http_5xx_count ?? '--'}
                          </div>
                          {statsWindow?.top_paths?.length ? (
                            <div className="settings-test-message">
                              Top: {statsWindow.top_paths.map((item: any) => item.path).join(', ')}
                            </div>
                          ) : (
                            <div className="settings-test-message">Top: --</div>
                          )}
                          <div className="settings-test-message">
                            SPOT proxy: {spotPollingStats?.count ?? '--'} req / {spotPollingStats?.requests_per_sec ?? '--'} rps / client {spotPollingStats?.unique_clients ?? '--'}
                          </div>
                          <div className="settings-test-message">
                            SPOT clients: {spotPollingClientText}
                          </div>
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
                          <div className="settings-test-message">
                            source: {stats?.errors?.source_counts ? Object.entries(stats.errors.source_counts).map(([key, value]) => `${key} ${value}`).join(', ') : '--'}
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
                          <span className="settings-comm-log-label">런타임 식별</span>
                        </div>
                        <div className="settings-test-meta">
                          <span>버전: {health?.app_version ?? '--'}</span>
                          <span>런타임: {health?.runtime_kind ?? '--'}</span>
                          <span>실행 파일: {health?.executable_path ?? '--'}</span>
                          <span>빌드 시각: {health?.executable_mtime ?? '--'}</span>
                        </div>
                      </div>
                      <div className="settings-observability-errors">
                        <div className="settings-comm-log-header">
                          <span className="settings-comm-log-label">에러 큐 상세</span>
                          <span className="settings-observability-count">
                            {observabilityErrors?.summary?.queue_size ?? 0}{LABELS.UNIT_CASES}
                          </span>
                        </div>
                        <div className="settings-test-message">
                          source: {observabilityErrors?.summary?.source_counts ? Object.entries(observabilityErrors.summary.source_counts).map(([key, value]) => `${key} ${value}`).join(', ') : '--'}
                        </div>
                        {observabilityLoading ? (
                          <div className="settings-error-empty">불러오는 중...</div>
                        ) : observabilityErrors?.items?.length ? (
                          <div className="settings-error-list">
                            {observabilityErrors.items.map((item: any, index: number) => (
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

                    <MemorySection
                      sectionRef={registerSettingsSection('settings-memory')}
                      health={health}
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
                      onRefresh={handleRefreshMemory}
                      onStartProfiler={handleStartMemoryProfiler}
                      onStopProfiler={handleStopMemoryProfiler}
                      onSnapshot={handleCaptureMemorySnapshot}
                      onExport={handleExportMemory}
                      onOpenFile={handleOpenMemoryExportFile}
                      onOpenFolder={handleOpenMemoryExportFolder}
                      onCopyPath={handleCopyMemoryExportPath}
                    />

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
                                spotImageMetadata,
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
                            <span>주기: {spotDiagnostics.refresh_interval_ms ?? '--'}ms / 다음: {formatTime(spotDiagnostics.next_fetch_scheduled_at)}</span>
                            <span>최근 시작: {formatTime(spotDiagnostics.last_fetch_started_at)} / 완료: {formatTime(spotDiagnostics.last_fetch_completed_at)}</span>
                            <span>지연: {spotDiagnostics.last_fetch_latency_ms ?? '--'}ms / 요청 {spotDiagnostics.fetch_count} / 오류 {spotDiagnostics.error_count}</span>
                            <span>상태: {spotDiagnostics.in_flight ? 'in-flight' : 'idle'} / 이유: {spotDiagnostics.last_fetch_reason ?? '--'}</span>
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
                          {securityStatusLabel}
                        </span>
                      </div>
                      <div className="settings-hint">{securityIntroText}</div>
                      
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
                            <span className="settings-field-help">비밀번호를 변경할 때만 현재 비밀번호를 입력합니다.</span>
                          </label>
                        )}
                        
                        {/* New Password - only enable input when current password is provided (if password was set) */}
                        <label className={`settings-field ${isSettingsFieldDirty('password') ? 'changed' : ''}`}>
                          {newPasswordLabel}
                          <div style={{ position: 'relative' }}>
                            <input
                              type={showNewPassword ? 'text' : 'password'}
                              placeholder={newPasswordPlaceholder}
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
                          <span className="settings-field-help">{newPasswordHelpText}</span>
                        </label>
                        
                        {/* Password Confirmation */}
                        {settingsForm.password.trim().length > 0 && (
                          <label className="settings-field">
                            비밀번호 확인
                            <div style={{ position: 'relative' }}>
                              <input
                                type={showConfirmPassword ? 'text' : 'password'}
                                placeholder={confirmPasswordPlaceholder}
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
                              <span className="settings-field-help" style={{ color: '#22c55e' }}>비밀번호가 일치합니다.</span>
                            )}
                          </label>
                        )}

                        {isCurrentPasswordMissing && (
                          <div className="settings-hint" style={{ color: '#fca5a5' }}>
                            변경하려면 현재 비밀번호를 먼저 입력하세요.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="settings-footer">
                <span className="settings-footer-note">{securityFooterNoteText}</span>
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
                    onClick={() => {
                      void handleSecuritySave();
                    }}
                    disabled={saveDisabled}
                    aria-disabled={saveDisabled}
                  >
                    저장
                  </button>
                </div>
              </div>
            </>
            )}
          </div>
        </div>
  );
}

export default SettingsModal;
