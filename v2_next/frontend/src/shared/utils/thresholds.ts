/**
 * 임계값 상태 관리 유틸리티
 */
import type { ConfigSnapshot, SettingsFormState, ThresholdKey, ThresholdEntry, ThresholdState } from '../types';
import { parseThresholdValue } from './validators';
import { LABELS } from '../constants/uiText';

export type ThresholdLevel = 'normal' | 'warn' | 'danger';

export const buildThresholdStateFromConfig = (thresholds?: ConfigSnapshot['values']['thresholds']): ThresholdState => {
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

export const buildThresholdStateFromForm = (form: SettingsFormState): ThresholdState => ({
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

export const isThresholdHit = (thresholds: ThresholdState, key: ThresholdKey, value: number | null | undefined) => {
  if (!thresholds.masterOn) {
    return false;
  }
  const entry = thresholds.entries[key];
  if (!entry?.enabled || entry.value === null) {
    return false;
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return false;
  }
  return value >= entry.value;
};

export const getThresholdValue = (thresholds: ThresholdState, key: ThresholdKey) => {
  if (!thresholds.masterOn) {
    return null;
  }
  const entry = thresholds.entries[key];
  if (!entry?.enabled || entry.value === null) {
    return null;
  }
  return entry.value;
};

export const THRESHOLD_LABELS: Record<ThresholdKey, string> = {
  speed: LABELS.SPEED,
  press: LABELS.PRESS,
  spot: LABELS.SPOT,
  temp_f: LABELS.CONTAINER_FRONT,
  temp_b: LABELS.CONTAINER_BACK,
  billet: LABELS.BILLET_LEN,
  billet_temp: LABELS.BILLET_TEMP,
  at_temp: LABELS.ENV_TEMP,
  at_pre: LABELS.ENV_HUMID,
  count: LABELS.COUNT,
  endpos: LABELS.END_POS,
};
