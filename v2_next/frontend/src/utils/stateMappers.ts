/**
 * State mapping utility functions extracted from App.tsx
 */

import type { LevelState, SpotState } from './stateMappers.types';

export type { LevelState, SpotState } from './stateMappers.types';

// ============ Constants ============

export const SPEED_LEVEL_MAP: Record<string, LevelState> = {
  very_fast: { label: '매우빠름', className: 'speed-very-fast' },
  fast: { label: '빠름', className: 'speed-fast' },
  normal: { label: '보통', className: 'speed-normal' },
  slow: { label: '저속', className: 'speed-slow' },
  very_slow: { label: '매우저속', className: 'speed-very-slow' },
  idle: { label: '대기', className: 'speed-idle' },
};

export const PRESS_LEVEL_MAP: Record<string, LevelState> = {
  high: { label: '높음', className: 'press-high' },
  normal: { label: '보통', className: 'press-normal' },
  low: { label: '낮음', className: 'press-low' },
  idle: { label: '대기', className: 'press-idle' },
};

export const SPOT_LEVEL_MAP: Record<string, SpotState> = {
  low: {
    label: '저온',
    statusClass: 'spot-status-low',
    fillClass: 'spot-fill-low',
    warning: false,
    sparkClass: 'sparkline-low',
  },
  normal: {
    label: '보통',
    statusClass: 'spot-status-normal',
    fillClass: 'spot-fill-normal',
    warning: false,
    sparkClass: 'sparkline-normal',
  },
  high: {
    label: '고온',
    statusClass: 'spot-status-high',
    fillClass: 'spot-fill-high',
    warning: false,
    sparkClass: 'sparkline-high',
  },
  warning: {
    label: '경고',
    statusClass: 'spot-status-warning',
    fillClass: 'spot-fill-warning',
    warning: true,
    sparkClass: 'sparkline-warning',
  },
  idle: {
    label: '대기',
    statusClass: 'spot-status-idle',
    fillClass: 'spot-fill-idle',
    warning: false,
    sparkClass: 'sparkline-idle',
  },
};

export const MOLD_LEVEL_CLASS: Record<string, string> = {
  alert: 'mold-alert',
  normal: 'mold-normal',
  muted: 'mold-muted',
};

export const ENV_TEMP_LEVEL_MAP: Record<string, LevelState> = {
  hot: { label: '더움', className: 'env-hot' },
  cold: { label: '추움', className: 'env-cold' },
  comfort: { label: '쾌적', className: 'env-comfort' },
  unknown: { label: '미확인', className: 'env-muted' },
};

export const ENV_PRE_LEVEL_MAP: Record<string, LevelState> = {
  humid: { label: '다습', className: 'env-humid' },
  dry: { label: '건조', className: 'env-dry' },
  comfort: { label: '쾌적', className: 'env-comfort' },
  unknown: { label: '미확인', className: 'env-muted' },
};

// ============ State Calculation Functions ============

export const getSpeedState = (speed: number): LevelState => {
  if (speed === 0) {
    return { label: '대기', className: 'speed-idle' };
  }
  if (speed >= 8) {
    return { label: '매우빠름', className: 'speed-very-fast' };
  }
  if (speed >= 6) {
    return { label: '빠름', className: 'speed-fast' };
  }
  if (speed >= 4) {
    return { label: '보통', className: 'speed-normal' };
  }
  if (speed >= 2) {
    return { label: '저속', className: 'speed-slow' };
  }
  return { label: '매우저속', className: 'speed-very-slow' };
};

export const getPressState = (press: number): LevelState => {
  if (press === 0) {
    return { label: '대기', className: 'press-idle' };
  }
  if (press >= 180) {
    return { label: '높음', className: 'press-high' };
  }
  if (press >= 126) {
    return { label: '보통', className: 'press-normal' };
  }
  return { label: '낮음', className: 'press-low' };
};

export const getSpotState = (
  temp: number,
  warningActive: boolean,
  warnTemp: number,
  highMin: number,
  normalMin: number
): SpotState => {
  if (!Number.isFinite(temp) || temp === 0) {
    return SPOT_LEVEL_MAP.idle;
  }
  if (temp >= warnTemp && warningActive) {
    return SPOT_LEVEL_MAP.warning;
  }
  if (temp >= highMin) {
    return SPOT_LEVEL_MAP.high;
  }
  if (temp >= normalMin) {
    return SPOT_LEVEL_MAP.normal;
  }
  return SPOT_LEVEL_MAP.low;
};

export const getMoldState = (value: number): { className: string } => {
  if (!Number.isFinite(value)) {
    return { className: 'mold-muted' };
  }
  return value >= 100 ? { className: 'mold-alert' } : { className: 'mold-normal' };
};

export const getEnvTempState = (value: number): LevelState => {
  if (!Number.isFinite(value)) {
    return { label: '미확인', className: 'env-muted' };
  }
  if (value >= 28) {
    return { label: '더움', className: 'env-hot' };
  }
  if (value < 10) {
    return { label: '추움', className: 'env-cold' };
  }
  return { label: '쾌적', className: 'env-comfort' };
};

export const getEnvHumidityState = (value: number): LevelState => {
  if (!Number.isFinite(value)) {
    return { label: '미확인', className: 'env-muted' };
  }
  if (value >= 60) {
    return { label: '다습', className: 'env-humid' };
  }
  if (value < 30) {
    return { label: '건조', className: 'env-dry' };
  }
  return { label: '쾌적', className: 'env-comfort' };
};

// ============ Level Mapping Functions ============

export const mapSpeedLevel = (level?: string): LevelState | null => {
  if (!level) return null;
  return SPEED_LEVEL_MAP[level] ?? null;
};

export const mapPressLevel = (level?: string): LevelState | null => {
  if (!level) return null;
  return PRESS_LEVEL_MAP[level] ?? null;
};

export const mapSpotLevel = (level?: string): SpotState | null => {
  if (!level) return null;
  return SPOT_LEVEL_MAP[level] ?? null;
};

export const mapMoldLevel = (level?: string): string | null => {
  if (!level) return null;
  return MOLD_LEVEL_CLASS[level] ?? null;
};

export const mapEnvTempLevel = (level?: string): LevelState | null => {
  if (!level) return null;
  return ENV_TEMP_LEVEL_MAP[level] ?? null;
};

export const mapEnvPreLevel = (level?: string): LevelState | null => {
  if (!level) return null;
  return ENV_PRE_LEVEL_MAP[level] ?? null;
};
