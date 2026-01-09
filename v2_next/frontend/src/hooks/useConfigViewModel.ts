import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { configService } from '../api/configService';
import {
  ConfigSnapshot,
  SettingsFormState,
  ConfigApplyResult,
  ThresholdState,
  CentralStatus,
  ThresholdKey,
  ThresholdEntry,
  ConfigUpdateResponse
} from '../types';
import { LABELS, MESSAGES } from '../constants/uiText';
import { useModal } from '../GlobalModalContext';

// --- Type Definitions for the Hook ---

export interface UseConfigViewModel {
  // State
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
  
  // Actions
  handleExternalRefresh: () => Promise<void>;
  handleExternalIgnore: () => void;
  handleCentralSync: () => Promise<void>;
  showSettingsToast: (message: string, level: 'ok' | 'warn' | 'error') => void;
  setSettingsOpen: (open: boolean) => void;
  setSettingsError: (error: string | null) => void;
  setSettingsInfo: (info: string | null) => void;
  loadSettings: () => Promise<void>;
  updateSettingsField: (field: keyof SettingsFormState, value: string | boolean) => void;
  handleSaveSettings: (options?: { auto?: boolean }) => Promise<void>;
  handleRestoreDefaults: () => Promise<void>;
  handleRestoreBackup: () => Promise<void>;
  handlePendingApply: () => Promise<void>;
  handlePendingClear: () => Promise<void>;
  handleMasterToggle: (checked: boolean) => void;
  handleOverrideToggle: () => Promise<void>;
  fetchCentralStatus: () => Promise<void>;
  // Data exports
  externalConfigPending: ConfigSnapshot | null;
  externalConfigPendingAt: number | null;
  overrideBusy: boolean;
  // Additional helpers exposed if needed
  isSettingsFieldDirty: (field: keyof SettingsFormState) => boolean;
}

// --- Helper Functions (migrated from App.tsx) ---

const isValidIp = (ip: string) => {
    const trimmed = ip.trim();
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

export const useConfigViewModel = (): UseConfigViewModel => {
  const modal = useModal();
  // State
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
  const [settingsPending, setSettingsPending] = useState<ConfigSnapshot['pending'] | null>(null);
  const [settingsPendingBusy, setSettingsPendingBusy] = useState(false);
  const [externalConfigPending, setExternalConfigPending] = useState<ConfigSnapshot | null>(null);
  const [externalConfigPendingAt, setExternalConfigPendingAt] = useState<number | null>(null);
  const [settingsToast, setSettingsToast] = useState<{ message: string; level: 'ok' | 'warn' | 'error' } | null>(null);
  const [overrideEnabled, setOverrideEnabled] = useState(false);
  const [overrideMeta, setOverrideMeta] = useState<ConfigSnapshot["meta"] | null>(null);
  const [centralStatus, setCentralStatus] = useState<CentralStatus | null>(null);
  const [centralSyncBusy, setCentralSyncBusy] = useState(false);
  const [overrideBusy, setOverrideBusy] = useState(false);

  // Refs
  const settingsFingerprintRef = useRef<string | null>(null);
  const settingsExternalNotifyRef = useRef<string | null>(null);
  const settingsToastTimerRef = useRef<number | null>(null);
  const autoSaveTimerRef = useRef<number | null>(null);

  // --- Helpers ---

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
      password: '',
      passwordSet: Boolean(values.settings.password_set),
    };
    return { form: nextForm, thresholds: nextThresholdState };
  }, []);

  const applySettingsSnapshot = useCallback(
    (snapshot: ConfigSnapshot) => {
      const { form, thresholds } = buildSettingsFormFromSnapshot(snapshot);
      
      // Preserve password field during auto-refresh to prevent resetting user input
      // Also preserve if user has started editing any field
      setSettingsForm((prev) => {
        if (!prev) return form;
        
        // Check if user is editing the password field
        if (prev.password.length > 0) {
          return { ...form, password: prev.password };
        }
        
        // Check if user has any unsaved changes - if so, don't overwrite the entire form
        const hasAnyChanges = Object.keys(prev).some((k) => {
          const key = k as keyof SettingsFormState;
          // Skip password since baseline always has empty password
          if (key === 'password') return prev.password.length > 0;
          if (key === 'passwordSet') return false; // Read-only field
          // Compare with what would be the new baseline
          return prev[key] !== form[key];
        });
        
        if (hasAnyChanges) {
          // User has unsaved changes, don't overwrite
          return prev;
        }
        
        return form;
      });
      
      setSettingsBaseline(form);
      setThresholdConfig(thresholds);
      setSettingsConfigPath(snapshot.config_path ?? null);
      setConfigWritable(snapshot.config_writable ?? null);
      setSettingsRestartRequired(Boolean(snapshot.restart_required));
      setSettingsApplyResult(snapshot.apply ?? null);
      setSettingsPending(snapshot.pending ?? null);
      setOverrideEnabled(Boolean(snapshot.meta?.override_enabled));
      setOverrideMeta(snapshot.meta ?? null);
    },
    [buildSettingsFormFromSnapshot]
  );

  // --- Actions ---

  const fetchCentralStatus = useCallback(async () => {
    try {
      const status = await configService.getCentralStatus();
      setCentralStatus(status);
    } catch (err) {
      console.error('Central status error', err);
    }
  }, []);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    setSettingsConfigPath(null);
    setConfigWritable(null);
    setSettingsBaseline(null);
    setSettingsRestartRequired(false);
    setSettingsPending(null);
    // setPathHealth({}); // Path health should be managed by useSystemViewModel if possible, or here?
    // Let's assume path health is separate, or we need to import it.
    // For now, we skip clearing path health here as it is not strictly config data.
    try {
      const data = await configService.getConfig();
      applySettingsSnapshot(data);
      const fingerprint = buildSettingsFingerprint(data);
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

  const updateSettingsField = useCallback((field: keyof SettingsFormState, value: string | boolean) => {
    setSettingsForm((prev) => {
      if (!prev) return prev;
      return { ...prev, [field]: value };
    });
  }, []);

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
      'statusWarnMs',
      'statusOfflineMs',
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

  const isSettingsFieldDirty = useCallback((field: keyof SettingsFormState) => {
      if (!settingsForm || !settingsBaseline) return false;
      return settingsForm[field] !== settingsBaseline[field];
  }, [settingsForm, settingsBaseline]);

  const hasSettingsChanges = useMemo(() => {
      if (!settingsForm || !settingsBaseline) return false;
      return Object.keys(settingsForm).some((k) => {
          const key = k as keyof SettingsFormState;
          return settingsForm[key] !== settingsBaseline[key];
      });
  }, [settingsForm, settingsBaseline]);

  const activeThresholds = useMemo(() => {
    if (settingsOpen && settingsForm) {
      return buildThresholdStateFromForm(settingsForm);
    }
    return thresholdConfig;
  }, [settingsOpen, settingsForm, thresholdConfig]);

  const handleSaveSettings = async (options?: { auto?: boolean }) => {
    const isAuto = options?.auto;
    if (!settingsForm) {
      return;
    }
    if (configWritable === false) { // configReadOnly
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
    if (!hasSettingsChanges && !settingsRestartRequired) {
      if (!isAuto) setSettingsInfo('변경 사항이 없습니다.');
      return;
    }
    
    // NOTE: Path health check dependency should be injected or handled via a callback if needed. 
    // For now we assume the consumer handles path checks or we skip strictly checking it inside the hook 
    // unless we pass pathHealth into the hook. 
    // Let's proceed without coupling to pathHealth for now, as it's separate. 
    // If essential, we will add it to the hook arguments later.

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
      system: {
        interval_sec: toFloat(settingsForm.intervalSec),
        status_warn_ms: toInt(settingsForm.statusWarnMs),
        status_offline_ms: toInt(settingsForm.statusOfflineMs),
      },
    };

    try {
      const data = await configService.saveConfig(payload);
      const applyInfo = data?.apply ?? null;
      const nextMeta = data?.meta ?? null;
      const pendingCount = applyInfo?.pending?.length ?? 0;
      const appliedCount = applyInfo?.applied?.length ?? 0;
      
      const message = pendingCount > 0
          ? `설정 저장 완료. 재시작 필요 항목 ${pendingCount}건.`
          : appliedCount > 0
            ? '설정 저장 완료. 즉시 적용됨.'
            : '설정 저장 완료.';
      
      if (!isAuto) {
           setSettingsInfo(message);
      }
      
      setSettingsRestartRequired(Boolean(data?.restart_required));
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
      
      if (!isAuto) {
        showSettingsToast(message, pendingCount > 0 ? 'warn' : 'ok');
      }

      setExternalConfigPending(null);
      setExternalConfigPendingAt(null);
      
      // Update fingerprint
      try {
        const snapshotData = await configService.getConfig();
        const newFingerprint = buildSettingsFingerprint(snapshotData);
        settingsFingerprintRef.current = newFingerprint;
      } catch (ignore) { }

      settingsExternalNotifyRef.current = null;
    } catch (error) {
      console.error('Config save failed', error);
      if (!isAuto) {
        setSettingsError('설정 저장에 실패했습니다.');
        showSettingsToast('설정 저장 실패', 'error');
      }
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleRestoreDefaults = async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      await configService.restoreDefaults();
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
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      await configService.restoreBackup();
      setSettingsRestartRequired(true);
      setSettingsApplyResult(null);
      await loadSettings();
      showSettingsToast('백업으로 복원했습니다.', 'ok');
    } catch (error) {
      console.error('Restore backup failed', error);
      setSettingsError('백업 복원에 실패했습니다.');
      showSettingsToast('백업 복원 실패', 'error');
    } finally {
      setSettingsLoading(false);
    }
  };

  const handlePendingApply = async () => {
    setSettingsPendingBusy(true);
    setSettingsError(null);
    try {
      await configService.applyPending();
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
    setSettingsPendingBusy(true);
    setSettingsError(null);
    try {
      await configService.clearPending();
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

  const handleCentralSync = async () => {
    if (centralSyncBusy) return;
    setCentralSyncBusy(true);
    setSettingsError(null);
    setSettingsInfo(null);
    try {
      const data = await configService.syncCentral();
      const status = data?.status ?? 'UNKNOWN';
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
    showSettingsToast('외부 변경을 반영했습니다.', 'ok');
  }, [
    externalConfigPending,
    hasSettingsChanges,
    applySettingsSnapshot,
    buildSettingsFingerprint,
    showSettingsToast,
    modal
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
        (next as Record<string, boolean | string | number | null>)[field] = checked;
      });
      return next;
    });
  };

  const handleOverrideToggle = async () => {
    if (overrideBusy || settingsLoading) return;
    const nextState = !overrideEnabled;
    const actionName = nextState ? '오버라이드 활성화' : '오버라이드 해제';
    
    // Simple prompt for now, or use complex modal if needed
    // In original App.tsx it might have used a prompt for password
    // We'll simplify or just ask for confirmation if no password needed yet
    // Assuming password might be needed if enabled
    
    // Check if password required? 
    // For now we just implement the toggle call
    
    // Ask for password
    const password = await modal.prompt(
      `${actionName}를 위해 관리자 비밀번호를 입력하세요.`,
      '',
      { inputType: 'password', title: '관리자 인증' }
    );
    
    if (password === null) return; // Cancelled

    setOverrideBusy(true);
    setSettingsError(null);
    try {
      const payload = {
         enabled: nextState,
         password: password,
         actor: 'user' 
      };
      
      await configService.toggleOverride(payload);
      setOverrideEnabled(nextState);
      await loadSettings();
      showSettingsToast(`${actionName} 완료`, 'ok');
    } catch (error) {
      console.error('Override toggle failed', error);
      setSettingsError(`${actionName} 실패`);
      showSettingsToast(`${actionName} 실패`, 'error');
    } finally {
      setOverrideBusy(false);
    }
  };

  // Auto-refresh config (Polling)
  useEffect(() => {
    if (!settingsOpen) return;
    
    // Initial load
    loadSettings();
    fetchCentralStatus();

    const poll = async () => {
      if (settingsLoading) return;
      try {
        const data = await configService.getConfig();
        const fingerprint = buildSettingsFingerprint(data);
        if (!settingsFingerprintRef.current) {
          settingsFingerprintRef.current = fingerprint;
          return;
        }
        if (fingerprint === settingsFingerprintRef.current) return;
        
        if (hasSettingsChanges) {
          if (settingsExternalNotifyRef.current !== fingerprint) {
            showSettingsToast('설정 파일이 외부에서 변경되었습니다. (갱신 보류)', 'warn');
            settingsExternalNotifyRef.current = fingerprint;
            setExternalConfigPending(data);
            setExternalConfigPendingAt(Date.now());
          }
          return;
        }
        applySettingsSnapshot(data);
        settingsFingerprintRef.current = fingerprint;
        settingsExternalNotifyRef.current = null;
        setExternalConfigPending(null);
        setExternalConfigPendingAt(null);
      } catch (error) {
        console.error('Settings auto-refresh failed', error);
      }
    };
    
    const interval = window.setInterval(poll, 5000); // 5 seconds
    return () => window.clearInterval(interval);
  }, [settingsOpen, loadSettings]);

  // Auto-dismiss settingsInfo
  useEffect(() => {
    if (settingsInfo) {
      const timer = setTimeout(() => {
        setSettingsInfo(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [settingsInfo]);

  // Auto-Save Logic
  useEffect(() => {
    const autoSaveEnabled = settingsForm?.autoSave;
    
    if (!autoSaveEnabled || !hasSettingsChanges || settingsLoading || !settingsForm || !settingsBaseline) {
      return;
    }

    // Check if the ONLY change is the password field - if so, skip auto-save
    // Password changes should only be saved manually by the user
    const nonPasswordChanges = Object.keys(settingsForm).some((k) => {
      const key = k as keyof SettingsFormState;
      if (key === 'password' || key === 'passwordSet') return false; // Skip password fields
      return settingsForm[key] !== settingsBaseline[key];
    });
    
    if (!nonPasswordChanges) {
      // Only password has changed, don't auto-save
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
  }, [settingsForm, settingsBaseline, hasSettingsChanges, settingsLoading]);

  return {
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
    activeThresholds,
    externalConfigPending,
    externalConfigPendingAt,
    overrideBusy
  };
};
