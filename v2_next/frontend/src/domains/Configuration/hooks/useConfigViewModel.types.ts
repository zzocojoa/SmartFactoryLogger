import type {
  CentralStatus,
  ConfigApplyResult,
  ConfigSnapshot,
  SettingsFormState,
  ThresholdState,
} from '../../../shared/types';

export interface SecuritySaveState {
  currentPassword: string;
  passwordConfirm: string;
}

export interface SaveSettingsOptions {
  auto?: boolean;
  security?: SecuritySaveState;
}

export interface UseConfigViewModel {
  settingsOpen: boolean;
  settingsLoading: boolean;
  settingsError: string | null;
  settingsInfo: string | null;
  settingsForm: SettingsFormState | null;
  settingsBaseline: SettingsFormState | null;
  settingsRestartRequired: boolean;
  settingsApplyResult: ConfigApplyResult | null;
  settingsPending: ConfigSnapshot['pending'] | null;
  settingsPendingBusy: boolean;
  settingsConfigPath: string | null;
  configWritable: boolean | null;
  overrideEnabled: boolean;
  overrideMeta: ConfigSnapshot['meta'] | null;
  centralStatus: CentralStatus | null;
  centralSyncBusy: boolean;
  thresholdConfig: ThresholdState;
  settingsToast: { message: string; level: 'ok' | 'warn' | 'error' } | null;
  hasSettingsChanges: boolean;
  validationErrors: Partial<Record<keyof SettingsFormState, string>>;
  hasValidationError: boolean;
  activeThresholds: ThresholdState;
  handleExternalRefresh: () => Promise<void>;
  handleExternalIgnore: () => void;
  handleCentralSync: () => Promise<void>;
  showSettingsToast: (message: string, level: 'ok' | 'warn' | 'error') => void;
  setSettingsOpen: (open: boolean) => void;
  setSettingsError: (error: string | null) => void;
  setSettingsInfo: (info: string | null) => void;
  loadSettings: () => Promise<void>;
  updateSettingsField: (field: keyof SettingsFormState, value: string | boolean) => void;
  handleSaveSettings: (options?: SaveSettingsOptions) => Promise<boolean>;
  handleRestoreDefaults: () => Promise<void>;
  handleRestoreBackup: () => Promise<void>;
  handlePendingApply: () => Promise<void>;
  handlePendingClear: () => Promise<void>;
  handleMasterToggle: (checked: boolean) => void;
  handleOverrideToggle: () => Promise<void>;
  fetchCentralStatus: () => Promise<void>;
  externalConfigPending: ConfigSnapshot | null;
  externalConfigPendingAt: number | null;
  overrideBusy: boolean;
  isSettingsFieldDirty: (field: keyof SettingsFormState) => boolean;
}
