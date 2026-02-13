import type { RecoveryMetrics } from './formatters.types';

export const formatNumber = (value: number, decimals: number): string => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return value.toFixed(decimals);
};

export const formatInteger = (value: number): string => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return Math.round(value).toString();
};

export const formatTime = (timestamp: number | null): string => {
  if (!timestamp) {
    return '--:--:--';
  }
  const date = new Date(timestamp);
  return date.toTimeString().slice(0, 8);
};

export const formatTimeFromSec = (value?: number | null): string => {
  if (!value) {
    return '--:--:--';
  }
  return formatTime(value * 1000);
};

export const formatAgeSec = (value?: number | null, nowMs?: number | null): string => {
  if (!value || !nowMs) {
    return '--';
  }
  const ageSec = Math.max(0, Math.round(nowMs / 1000 - value));
  return `${ageSec}s`;
};

export const formatOptionalNumber = (value?: number | null, decimals: number = 0): string => {
  if (value === undefined || value === null) {
    return '--';
  }
  return formatNumber(value, decimals);
};

export const formatOptionalSeconds = (value?: number | null): string => {
  if (value === undefined || value === null) {
    return '--';
  }
  return `${Math.round(value)}s`;
};

export const formatOptionalText = (value?: string | null): string => {
  const trimmed = (value ?? '').trim();
  return trimmed ? trimmed : '--';
};

export const formatMetaTime = (value?: string | null): string => {
  if (!value) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const formatted = date.toLocaleString();
  return formatted;
};

export const calcRecoverySec = (metrics?: RecoveryMetrics): number | null => {
  if (!metrics) {
    return null;
  }
  if (metrics.last_recovery_sec !== undefined && metrics.last_recovery_sec !== null) {
    return metrics.last_recovery_sec;
  }
  if (metrics.last_error_time && metrics.last_success_time) {
    if (metrics.last_success_time > metrics.last_error_time) {
      return metrics.last_success_time - metrics.last_error_time;
    }
  }
  return null;
};

export const calcPercent = (value: number, max: number): number => {
  if (max <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, (value / max) * 100));
};

export const clampNumber = (value: number, min: number, max: number): number => {
  return Math.max(min, Math.min(max, value));
};
