import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { configService } from '../api/configService';
import {
  ConfigSnapshot,
  SettingsFormState,
  ConfigApplyResult,
  ThresholdState,
  CentralStatus,
  ConfigUpdateResponse
} from '../../../shared/types';
import { LABELS, MESSAGES } from '../../../shared/constants/uiText';
import { useModal } from '../../../shared/hooks/useGlobalModalContext';
import {
  isValidIp,
  isValidNumberInput,
  isValidPort,
  parseThresholdValue,
} from '../../../shared/utils/validators';
import {
  buildThresholdStateFromConfig,
  buildThresholdStateFromForm,
} from './useConfigViewModel.selectors';
import { buildSettingsFingerprint } from './useConfigViewModel.service';
import {
  useConfigAutoRefreshEffect,
  useConfigInfoAutoDismissEffect,
} from './useConfigViewModelEffects';
import type {
  SaveSettingsOptions,
  UseConfigViewModel,
} from './useConfigViewModel.types';

const isPositiveIntegerInput = (value: string): boolean => {
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return false;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) && parsed > 0;
};

const toOptionalNumberText = (value: number | null | undefined): string => {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
};

const toInt = (value: string): number | undefined => {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return undefined;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const toPositiveInt = (value: string): number | undefined => {
  const parsed = toInt(value);
  if (parsed === undefined || parsed <= 0) {
    return undefined;
  }
  return parsed;
};

const toFloat = (value: string): number | undefined => {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return undefined;
  }
  const parsed = Number.parseFloat(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
};

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
      spotActuatorStep: toOptionalNumberText(values.spot.actuator_step),
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
      statusWarnMs: String(values.system?.status_warn_ms ?? 10000),
      statusOfflineMs: String(values.system?.status_offline_ms ?? 20000),
      password: '',
      passwordSet: values.settings.password_set ?? false,
      mesEnabled: values.mes?.enabled ?? false,
      mesUserId: values.mes?.userid ?? '',
      mesPassword: '',
      mesPasswordSet: values.mes?.password_set ?? false,
      mesStartHour: String(values.mes?.starthour ?? 8),
      mesEndHour: String(values.mes?.endhour ?? 19),
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
        // BUG FIX: Also preserve mesPassword
        const preservePassword = prev.password.length > 0;
        const preserveMesPassword = prev.mesPassword.length > 0;
        
        if (preservePassword || preserveMesPassword) {
            return { 
                ...form, 
                password: preservePassword ? prev.password : form.password,
                mesPassword: preserveMesPassword ? prev.mesPassword : form.mesPassword
            };
        }
        
        // Check if user has any unsaved changes - if so, don't overwrite the entire form
        const hasAnyChanges = Object.keys(prev).some((k) => {
          const key = k as keyof SettingsFormState;
          // Skip password since baseline always has empty password
          if (key === 'password') return prev.password.length > 0;
          if (key === 'mesPassword') return prev.mesPassword.length > 0; // Fix: Treat mesPassword like password
          if (key === 'passwordSet') return false; // Read-only field
          if (key === 'mesPasswordSet') return false; // Fix: Read-only field
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

  const applySettingsSnapshotRef = useRef(applySettingsSnapshot);
  const buildSettingsFingerprintRef = useRef(buildSettingsFingerprint);

  useEffect(() => {
    applySettingsSnapshotRef.current = applySettingsSnapshot;
  }, [applySettingsSnapshot]);

  useEffect(() => {
    buildSettingsFingerprintRef.current = buildSettingsFingerprint;
  }, [buildSettingsFingerprint]);

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
      applySettingsSnapshotRef.current(data);
      const fingerprint = buildSettingsFingerprintRef.current(data);
      settingsFingerprintRef.current = fingerprint;
      settingsExternalNotifyRef.current = null;
      setExternalConfigPending(null);
      setExternalConfigPendingAt(null);
      return true;
    } catch (error) {
      console.error('Config load failed', error);
      setSettingsError('???깆젧???釉띾쐞???? 嶺뚮쪇沅?쭛???鍮??');
      return false;
    } finally {
      setSettingsLoading(false);
    }
  }, []);

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
      errors.extruderIp = 'IPv4 ?筌먦끇六???熬곣뫀六???덈펲.';
    }
    if (!isValidPort(settingsForm.extruderPort)) {
      errors.extruderPort = '1-65535 ?뺢퀡???낅ご????놁졑??琉얠돪??';
    }
    if (!isValidIp(settingsForm.lsIp)) {
      errors.lsIp = 'IPv4 ?筌먦끇六???熬곣뫀六???덈펲.';
    }
    if (!isValidPort(settingsForm.lsPort)) {
      errors.lsPort = '1-65535 ?뺢퀡???낅ご????놁졑??琉얠돪??';
    }
    if (!isValidIp(settingsForm.spotIp)) {
      errors.spotIp = 'IPv4 ?筌먦끇六???熬곣뫀六???덈펲.';
    }
    if (!isPositiveIntegerInput(settingsForm.spotActuatorStep)) {
      errors.spotActuatorStep = '양의 정수를 입력하세요.';
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
      'thresholdAtPreValue',
      'thresholdCountValue',
      'thresholdEndPosValue',
      'statusWarnMs',
      'statusOfflineMs',
    ];
    thresholdValueFields.forEach((field) => {
      const value = settingsForm[field] as string;
      if (!isValidNumberInput(value)) {
        errors[field] = '????썹춯????놁졑??琉얠돪??';
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

  const handleSaveSettings = async (options?: SaveSettingsOptions): Promise<boolean> => {
    const isAuto = options?.auto;
    const trimmedCurrentPassword = options?.security?.currentPassword.trim() ?? '';
    const trimmedPasswordConfirm = options?.security?.passwordConfirm.trim() ?? '';
    if (!settingsForm) {
      return false;
    }
    if (configWritable === false) {
      if (!isAuto) setSettingsError('설정 파일이 읽기 전용입니다.');
      return false;
    }
    if (hasValidationError) {
      if (!isAuto) setSettingsError('입력값을 확인하세요.');
      return false;
    }
    if (!overrideEnabled && hasSettingsChanges) {
      if (!isAuto) setSettingsError('저장하려면 오버라이드를 켜야 합니다.');
      return false;
    }
    if (!hasSettingsChanges && !settingsRestartRequired) {
      if (!isAuto) setSettingsInfo('변경된 내용이 없습니다.');
      return false;
    }
    
    const nextPassword = settingsForm.password.trim();
    const hasPasswordChange = nextPassword.length > 0;
    const requiresCurrentPassword = settingsForm.passwordSet && hasPasswordChange;
    const hasPasswordConfirmMismatch =
      hasPasswordChange && trimmedPasswordConfirm !== nextPassword;

    if (hasPasswordConfirmMismatch) {
      if (!isAuto) {
        setSettingsError('새 비밀번호와 확인 비밀번호가 일치하지 않습니다.');
      }
      return false;
    }

    if (requiresCurrentPassword && trimmedCurrentPassword.length === 0) {
      if (!isAuto) {
        setSettingsError('기존 비밀번호를 변경하려면 현재 비밀번호를 입력해야 합니다.');
      }
      return false;
    }

    if (requiresCurrentPassword) {
      try {
        await configService.verifyPassword(trimmedCurrentPassword);
      } catch (error: unknown) {
        if (!isAuto) {
          const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
          setSettingsError(detail || '현재 비밀번호가 일치하지 않습니다.');
        }
        return false;
      }
    }

    // NOTE: Path health check dependency should be injected or handled via a callback if needed. 
    // For now we assume the consumer handles path checks or we skip strictly checking it inside the hook 
    // unless we pass pathHealth into the hook. 
    // Let's proceed without coupling to pathHealth for now, as it's separate. 
    // If essential, we will add it to the hook arguments later.

    const spotActuatorStep = toPositiveInt(settingsForm.spotActuatorStep);
    if (spotActuatorStep === undefined) {
      if (!isAuto) setSettingsError('?묒쓽 ?뺤닔瑜??낅젰?섏꽭??');
      return false;
    }

    setSettingsLoading(true);
    setSettingsError(null);
    setSettingsInfo(null);

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
        actuator_step: spotActuatorStep,
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
        current_password: requiresCurrentPassword ? trimmedCurrentPassword : undefined,
      },
      logging: {
        rotation_enabled: settingsForm.rotationEnabled,
        rotation_mode: settingsForm.rotationMode,
        cycle_idle_time: toFloat(settingsForm.cycleIdleTime),
        cycle_threshold_press: toFloat(settingsForm.cycleThresholdPress),
      },
      system: {
        interval_sec: parseThresholdValue(settingsForm.intervalSec) ?? 0.2, // Use parseThresholdValue helper
        status_warn_ms: toInt(settingsForm.statusWarnMs),
        status_offline_ms: toInt(settingsForm.statusOfflineMs),
      },
      mes: {
        enabled: settingsForm.mesEnabled,
        userid: settingsForm.mesUserId.trim() || undefined,
        password: settingsForm.mesPassword.trim() || undefined,
        starthour: toInt(settingsForm.mesStartHour) ?? 8,
        endhour: toInt(settingsForm.mesEndHour) ?? 19,
      }
    };

    try {
      const data = (await configService.saveConfig(payload)) as ConfigUpdateResponse;
      const applyInfo = data?.apply ?? null;
      const nextMeta = data?.meta ?? null;
      const pendingCount = applyInfo?.pending?.length ?? 0;
      const appliedCount = applyInfo?.applied?.length ?? 0;
      const saveMessage = pendingCount > 0
        ? `설정이 저장되었지만 즉시 적용되지 않은 항목이 ${pendingCount}건 있습니다.`
        : appliedCount > 0
          ? '설정이 저장되고 즉시 적용되었습니다.'
          : '설정이 저장되었습니다.';
      
      const message = pendingCount > 0
          ? `???깆젧 ?????熬곣뫁?? ??????熬곣뫗??????${pendingCount}濾?`
          : appliedCount > 0
            ? '???깆젧 ?????熬곣뫁?? 嶺뚯빖留????⑤챷???'
            : '???깆젧 ?????熬곣뫁??';
      
      if (!isAuto) {
           setSettingsInfo(saveMessage);
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
        mesPassword: '',
      });
      setThresholdConfig(buildThresholdStateFromForm(settingsForm));
      updateSettingsField('password', '');
      updateSettingsField('mesPassword', '');
      
      if (!isAuto) {
        showSettingsToast(saveMessage, pendingCount > 0 ? 'warn' : 'ok');
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
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      const errorMessage = typeof detail === 'string' && detail.trim().length > 0
        ? detail
        : '설정을 저장하지 못했습니다.';
      if (!isAuto) {
        setSettingsError('설정을 저장하지 못했습니다.');
        showSettingsToast('설정 저장에 실패했습니다.', 'error');
      }
      return false;
      if (!isAuto) {
        setSettingsError('???깆젧 ????쒑굢????덉넮???곕????덈펲.');
        showSettingsToast('???깆젧 ???????덉넮', 'error');
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
      showSettingsToast('?リ옇???泥롨첋?뚮さ???곌랜踰????곕????덈펲.', 'ok');
    } catch (error) {
      console.error('Restore defaults failed', error);
      setSettingsError('?リ옇???泥??곌랜踰??????덉넮???곕????덈펲.');
      showSettingsToast('?リ옇???泥??곌랜踰?????덉넮', 'error');
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
      showSettingsToast('?꾩룄??캆??怨쀬Ŧ ?곌랜踰????곕????덈펲.', 'ok');
    } catch (error) {
      console.error('Restore backup failed', error);
      setSettingsError('?꾩룄??캆??곌랜踰??????덉넮???곕????덈펲.');
      showSettingsToast('?꾩룄??캆??곌랜踰?????덉넮', 'error');
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
      showSettingsToast('?곌랜?筌?????깆젧????⑤챷????곕????덈펲.', 'ok');
    } catch (error) {
      console.error('Pending apply failed', error);
      setSettingsError('?곌랜?筌?????깆젧 ??⑤챷??????덉넮???곕????덈펲.');
      showSettingsToast('?곌랜?筌?????깆젧 ??⑤챷?????덉넮', 'error');
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
      showSettingsToast('?곌랜?筌?????깆젧????????곕????덈펲.', 'ok');
    } catch (error) {
      console.error('Pending clear failed', error);
      setSettingsError('?곌랜?筌?????깆젧 ????????덉넮???곕????덈펲.');
      showSettingsToast('?곌랜?筌?????깆젧 ???????덉넮', 'error');
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
      const ok = await modal.confirm('?筌? ?곌떠?????怨몃뮔???釉띾쐞????좊듆 ?熬곣뫗?????놁졑 繞벿살탳???띠룆???????륁??얜Ŧ鍮?? ??ｌ뫒???ル맪???', {
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
    showSettingsToast('?筌? ?곌떠??롪퍔????꾩룇瑗????곕????덈펲.', 'ok');
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
    showSettingsToast('?筌? ?곌떠??????逾???곌랜?筌???곕????덈펲.', 'warn');
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
    const actionName = nextState ? 'Enable override' : 'Disable override';
    
    // Simple prompt for now, or use complex modal if needed
    // In original App.tsx it might have used a prompt for password
    // We'll simplify or just ask for confirmation if no password needed yet
    // Assuming password might be needed if enabled
    
    // Check if password required? 
    // For now we just implement the toggle call
    
    // Ask for password
    const password = await modal.prompt(
      `${actionName} requires admin password.`, 
      '',
      { inputType: 'password', title: 'Admin Authentication' }
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
      showSettingsToast(`${actionName} completed`, 'ok');
    } catch (error) {
      console.error('Override toggle failed', error);
      setSettingsError(`${actionName} failed`);
      showSettingsToast(`${actionName} failed`, 'error');
    } finally {
      setOverrideBusy(false);
    }
  };

  useConfigAutoRefreshEffect({
    settingsOpen,
    settingsLoading,
    loadSettings,
    fetchCentralStatus,
    hasSettingsChanges,
    buildSettingsFingerprint,
    applySettingsSnapshot,
    showSettingsToast,
    settingsFingerprintRef,
    settingsExternalNotifyRef,
    setExternalConfigPending,
    setExternalConfigPendingAt,
  });

  useConfigInfoAutoDismissEffect({ settingsInfo, setSettingsInfo });

  // Auto-Save Logic
  // Auto-Save Logic REMOVED:
  // The 'autoSave' setting controls backend CSV logging behavior, not the UI form.
  // UI changes must be saved manually by clicking the Save button.

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

