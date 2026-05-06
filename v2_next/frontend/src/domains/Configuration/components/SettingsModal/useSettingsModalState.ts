/**
 * useSettingsModalState – extracted from App.tsx (Phase 12)
 *
 * Provides computed values that are consumed exclusively by the
 * Settings Modal UI.  Keeping them co-located with the modal
 * removes ~200 lines from App.tsx without changing behaviour.
 */
import { useMemo, useCallback } from 'react';
import type { SettingsFormState } from '../../../../shared/types';
import { formatMetaTime } from '../../../../shared/utils/formatters';
import { CONFIG_LABELS, LABELS } from '../../../../shared/constants/uiText';

// ─── Types ────────────────────────────────────────────────────────

export interface SettingsModalStateOptions {
  settingsForm: SettingsFormState | null;
  settingsBaseline: SettingsFormState | null;
  settingsApplyResult: { applied?: string[]; pending?: string[] } | null;
  overrideMeta: { last_sync?: string | null } | null | undefined;
  pathHealth: any;
  hasSettingsChanges: boolean;
  isSettingsFieldDirty: (field: keyof SettingsFormState) => boolean;
}

// ─── Section → Field mapping ─────────────────────────────────────

const SECTION_FIELD_MAP: Record<string, Array<keyof SettingsFormState>> = {
  'settings-summary': [],
  'settings-central': [],
  'settings-comm': ['extruderIp', 'extruderPort', 'lsIp', 'lsPort'],
  'settings-observability': [],
  'settings-memory': [],
  'settings-spot': ['spotIp', 'spotRefreshInterval', 'spotActuatorStep'],
  'settings-storage': [
    'logPath',
    'snapshotPath',
    'autoSave',
    'intervalSec',
    'statusWarnMs',
    'statusOfflineMs',
  ],
  'settings-logging': [
    'rotationEnabled',
    'rotationMode',
    'cycleIdleTime',
    'cycleThresholdPress',
  ],
  'settings-mes': [
    'mesEnabled',
    'mesUserId',
    'mesPassword',
    'mesStartHour',
    'mesEndHour',
  ],
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
};

// ─── Label map (change-summary) ──────────────────────────────────

const LABEL_MAP: Record<keyof SettingsFormState, string> = {
  extruderIp: 'Extruder IP',
  extruderPort: 'Extruder Port',
  lsIp: 'LS PLC IP',
  lsPort: 'LS PLC Port',
  spotIp: 'SPOT IP',
  spotRefreshInterval: 'SPOT Refresh (sec)',
  spotActuatorStep: CONFIG_LABELS.SPOT_ACTUATOR_STEP,
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

const DIRTY_KEYS: Array<keyof SettingsFormState> = [
  'extruderIp',
  'extruderPort',
  'lsIp',
  'lsPort',
  'spotIp',
  'spotRefreshInterval',
  'spotActuatorStep',
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

// ─── Helpers ─────────────────────────────────────────────────────

function formatValue(value: string | boolean) {
  if (typeof value === 'boolean') {
    return value ? '사용' : '미사용';
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : '(비어 있음)';
}

const CHANGE_SUMMARY_KEYS: Array<keyof SettingsFormState> = [
  'extruderIp',
  'extruderPort',
  'lsIp',
  'lsPort',
  'spotIp',
  'spotRefreshInterval',
  'spotActuatorStep',
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

// ─── Hook ────────────────────────────────────────────────────────

export function useSettingsModalState(opts: SettingsModalStateOptions) {
  const {
    settingsForm,
    settingsBaseline,
    settingsApplyResult,
    overrideMeta,
    hasSettingsChanges,
    isSettingsFieldDirty,
  } = opts;

  /* ── dirty count ── */
  const settingsDirtyCount = useMemo(() => {
    if (!settingsForm || !settingsBaseline) {
      return 0;
    }
    return DIRTY_KEYS.reduce((count, key) => {
      if (key === 'password' || key === 'mesPassword') {
        return settingsForm[key].trim() ? count + 1 : count;
      }
      if (key === 'passwordSet') {
        return count;
      }
      const current = settingsForm[key];
      const baseline = settingsBaseline[key];
      if (typeof current === 'boolean' || typeof baseline === 'boolean') {
        return current !== baseline ? count + 1 : count;
      }
      return String(current ?? '').trim() !== String(baseline ?? '').trim()
        ? count + 1
        : count;
    }, 0);
  }, [settingsForm, settingsBaseline]);

  /* ── section field map (static) ── */
  const settingsSectionFieldMap = SECTION_FIELD_MAP;

  /* ── per-section "has changes" ── */
  const settingsSectionHasChanges = useMemo(() => {
    const result: Record<string, boolean> = {};
    Object.entries(settingsSectionFieldMap).forEach(([sectionId, fields]) => {
      if (sectionId === 'settings-summary') {
        result[sectionId] = hasSettingsChanges;
        return;
      }
      result[sectionId] = fields.some((field) =>
        isSettingsFieldDirty(field as keyof SettingsFormState),
      );
    });
    return result;
  }, [settingsSectionFieldMap, isSettingsFieldDirty, hasSettingsChanges]);

  /* ── summary cards ── */
  const buildSettingsSummaryCards = useCallback(() => {
    if (!settingsForm) {
      return [];
    }
    const appliedCount = settingsApplyResult?.applied?.length ?? 0;
    const pendingCount = settingsApplyResult?.pending?.length ?? 0;
    const applyStatus =
      pendingCount > 0
        ? '재시작 필요'
        : appliedCount > 0
          ? '즉시 반영'
          : '저장 전';
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
        title: '저장 요약',
        items: [
          `로그: ${settingsForm.logPath || '-'}`,
          `스냅샷: ${settingsForm.snapshotPath || '-'}`,
        ],
      },
      {
        title: 'SPOT 요약',
        items: [
          `IP: ${settingsForm.spotIp || '-'}`,
          `새로고침: ${settingsForm.spotRefreshInterval || '-'}초`,
          `액추에이터 스텝: ${settingsForm.spotActuatorStep || '-'}`,
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

  /* ── change summary lines ── */
  const buildSettingsChangeSummary = useCallback(() => {
    if (!settingsForm || !settingsBaseline) {
      return [] as string[];
    }
    const summary: string[] = [];
    CHANGE_SUMMARY_KEYS.forEach((key) => {
      if (key === 'password') {
        if (settingsForm.password.trim()) {
          summary.push(`${LABEL_MAP.password}: 변경됨`);
        }
        return;
      }
      if (key === 'mesPassword') {
        if (settingsForm.mesPassword.trim()) {
          summary.push(`${LABEL_MAP.mesPassword}: 변경됨`);
        }
        return;
      }
      if (!isSettingsFieldDirty(key)) {
        return;
      }
      const before = formatValue(settingsBaseline[key]);
      const after = formatValue(settingsForm[key]);
      summary.push(`${LABEL_MAP[key]}: ${before} → ${after}`);
    });
    return summary;
  }, [settingsForm, settingsBaseline, isSettingsFieldDirty]);

  /* ── path health ── */
  const { pathHealth } = opts;
  const hasPathError = useMemo(() => 
    ['log', 'snapshot'].some(key => pathHealth[key]?.status === 'ERROR'),
    [pathHealth]
  );
  const hasPathWarn = useMemo(() => 
    ['log', 'snapshot'].some(key => pathHealth[key]?.status === 'WARN'),
    [pathHealth]
  );
  const logPathFieldState = useMemo(() => {
    const s = pathHealth.log?.status;
    return s === 'ERROR' ? 'error' : s === 'WARN' ? 'warn' : '';
  }, [pathHealth.log]);
  const snapshotPathFieldState = useMemo(() => {
    const s = pathHealth.snapshot?.status;
    return s === 'ERROR' ? 'error' : s === 'WARN' ? 'warn' : '';
  }, [pathHealth.snapshot]);

  /* ── apply details ── */
  const applyDetails = useMemo(() => {
    const applied = settingsApplyResult?.applied || [];
    const pending = settingsApplyResult?.pending || [];
    const format = (key: string) => APPLY_KEY_LABELS[key] ?? key;
    return {
      applied: applied.map(format),
      pending: pending.map(format),
    };
  }, [settingsApplyResult]);

  return {
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
  };
}
