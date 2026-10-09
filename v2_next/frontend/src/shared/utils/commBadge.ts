/**
 * 통신 상태 배지와 카메라 상태 유틸리티
 */
import type { SpotImageResponseMetadata } from '../../domains/FacilityData/api/spotService.types';
import type { CommChannelMetrics, CommSpotMetrics, HealthReceiptTiming, SpotConfig, SpotTemperatureHealth } from '../types';
import { formatAgeSec, formatOptionalSeconds, formatTimeFromSec } from './formatters';

export type CommBadge = {
  key: string;
  text: string;
  title: string;
  state: 'ok' | 'warn' | 'error' | 'idle';
};

export type SpotStatusDetail = { label: string; value: string };

type CameraStatus = {
  type: 'error' | 'loading';
  title: string;
  detail: string;
};

const parseCameraStatusMessage = (message: string): CameraStatus => {
  const [title, ...detailParts] = message.split('\n');
  const normalizedTitle = title.trim();
  const detail = detailParts.join(' ').trim();
  return {
    type: 'error',
    title: normalizedTitle || message,
    detail,
  };
};

export const buildCommBadge = (
  key: string,
  metrics?: CommChannelMetrics,
  nowMs?: number | null
): CommBadge => {
  if (!metrics) {
    return { key, text: `${key} --`, title: `${key}: no data`, state: 'idle' };
  }

  const connected = Boolean(metrics.connected);
  const failures = (metrics.connect_failures ?? 0) + (metrics.read_failures ?? 0);
  const hasError = Boolean(metrics.last_error_time || failures > 0);
  const state: CommBadge['state'] = connected ? 'ok' : hasError ? 'error' : 'warn';
  const backoff = metrics.backoff_sec ?? 0;
  const recoveryCount = metrics.recovery_count ?? 0;
  const totalDowntime = metrics.total_downtime_sec ?? null;
  const currentDowntime = metrics.current_downtime_sec ?? null;
  const lastDisconnect = metrics.last_disconnect_time ?? null;
  const lastRecoveryAt = metrics.last_recovery_at ?? null;
  const mergeState = metrics.merge_blocks === undefined ? '' : `Merge ${metrics.merge_blocks ? 'ON' : 'OFF'}`;
  const titleParts = [
    `${key} ${connected ? '연결됨' : '끊김'}`,
    `실패 ${failures}`,
    `백오프 ${backoff}s`,
    `마지막 오류 ${formatTimeFromSec(metrics.last_error_time)}`,
    `오류 경과 ${formatAgeSec(metrics.last_error_time ?? null, nowMs ?? null)}`,
    `복구 횟수 ${recoveryCount}`,
    `다운타임 ${formatOptionalSeconds(currentDowntime)} / 누적 ${formatOptionalSeconds(totalDowntime)}`,
    `최근 끊김 ${formatTimeFromSec(lastDisconnect)}`,
    `최근 복구 ${formatTimeFromSec(lastRecoveryAt)}`,
  ];

  if (metrics.last_recovery_sec !== null && metrics.last_recovery_sec !== undefined) {
    titleParts.push(`복구 시간 ${Math.round(metrics.last_recovery_sec)}s`);
  }
  if (mergeState) {
    titleParts.push(mergeState);
  }
  if (metrics.last_error) {
    titleParts.push(`메시지 ${metrics.last_error}`);
  }

  return {
    key,
    text: `${key} ${connected ? 'OK' : 'DOWN'}`,
    title: titleParts.join(' | '),
    state,
  };
};

const isNonNegativeNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0;

const knownOptional = (value: unknown, choices: string[]): boolean =>
  value === undefined || (typeof value === 'string' && choices.includes(value));

const diagnosticText = (value: unknown, fallback = 'unknown'): string =>
  typeof value === 'string' ? value : fallback;

export const buildSpotStatusBadges = (params: {
  observation?: SpotTemperatureHealth;
  metrics?: CommSpotMetrics;
  receipt?: HealthReceiptTiming | null;
  monotonicNowMs: number;
  refreshMs?: number | null;
  apiDegraded?: boolean;
}): { commBadge: CommBadge; temperatureBadge: CommBadge; details: SpotStatusDetail[] } => {
  const { observation: spot, metrics, receipt, monotonicNowMs, refreshMs, apiDegraded } = params;
  const elapsedMs = receipt && isNonNegativeNumber(receipt.receivedAtMonotonicMs)
    && isNonNegativeNumber(receipt.ageAtReceiptMs)
    && isNonNegativeNumber(monotonicNowMs) && monotonicNowMs >= receipt.receivedAtMonotonicMs
    ? monotonicNowMs - receipt.receivedAtMonotonicMs + receipt.ageAtReceiptMs : null;
  const snapshotAgeMs = spot && isNonNegativeNumber(spot.spot_snapshot_age_ms) && elapsedMs !== null
    ? spot.spot_snapshot_age_ms + elapsedMs : null;
  const valueAgeMs = spot && isNonNegativeNumber(spot.spot_value_age_ms) && elapsedMs !== null
    ? spot.spot_value_age_ms + elapsedMs : null;
  const readFailures = metrics?.read_failures;
  const details: SpotStatusDetail[] = [
    { label: 'poll', value: diagnosticText(spot?.spot_poll_status) },
    { label: 'raw', value: diagnosticText(spot?.spot_raw_validity) },
    { label: 'source', value: diagnosticText(spot?.spot_source_freshness) },
    { label: '관측 경과', value: snapshotAgeMs === null ? '--' : `${(snapshotAgeMs / 1000).toFixed(1)}s` },
    { label: '장비', value: diagnosticText(spot?.spot_device_status_code, '--') },
    { label: '온도 상태', value: diagnosticText(spot?.temperature_status_shadow) },
    { label: 'origin', value: diagnosticText(spot?.temperature_value_origin) },
    { label: 'cache', value: diagnosticText(spot?.spot_cache_status) },
    { label: '값 경과', value: valueAgeMs === null ? '--' : `${(valueAgeMs / 1000).toFixed(1)}s` },
    { label: '최근 유효 온도', value: formatTimeFromSec(spot?.temperature_last_success_at ?? metrics?.last_success_time) },
    { label: '최근 오류', value: formatTimeFromSec(spot?.temperature_last_error_at ?? metrics?.last_error_time) },
    { label: '오류', value: `${diagnosticText(spot?.temperature_last_error_code, '--')} / 누적 실패 ${isNonNegativeNumber(readFailures) ? readFailures : 0}` },
    ...(apiDegraded ? [{ label: 'API 상태', value: 'health API 갱신 지연: 마지막 수신 관측 기준' }] : []),
  ];
  const detail = details.map(({ label, value }) => `${label} ${value}`).join(' | ');
  const result = (comm: string, temperature: string, commState: CommBadge['state'], tempState: CommBadge['state']) => ({
    commBadge: { key: 'SPOT', text: `SPOT ${comm}`, title: `SPOT ${comm} | ${detail}`, state: commState },
    temperatureBadge: { key: 'Temp', text: `Temp ${temperature}`, title: `Temp ${temperature} | ${detail}`, state: tempState },
    details,
  });
  const unknown = () => result('UNKNOWN', 'UNKNOWN', 'idle', 'idle');
  if (!spot || spot.diagnostics_available === false
    || !knownOptional(spot.temperature_status_shadow, ['ok', 'no_target', 'startup_pending', 'source_error', 'invalid_value', 'stale', 'unknown_missing'])
    || !knownOptional(spot.spot_cache_status, ['fresh', 'reused', 'expired', 'empty', 'invalidated', 'available_not_used'])
    || !knownOptional(spot.temperature_value_origin, ['current_observation', 'cached_observation', 'none'])) {
    return unknown();
  }
  if (spot.spot_poll_status === 'not_attempted') return result('WAIT', 'WAIT', 'warn', 'idle');
  if (spot.spot_poll_status === 'config_missing') return result('CONFIG', 'SOURCE_ERROR', 'warn', 'error');
  const thresholdSec = spot.spot_poll_freshness_threshold_sec;
  const thresholdMs = thresholdSec === undefined
    ? (refreshMs === null || refreshMs === undefined ? 3000 : refreshMs * 3)
    : (isNonNegativeNumber(thresholdSec) && thresholdSec > 0 ? thresholdSec * 1000 : NaN);
  if (!Number.isFinite(thresholdMs) || thresholdMs <= 0 || snapshotAgeMs === null
    || (spot.spot_source_freshness !== 'fresh' && spot.spot_source_freshness !== 'stale')
    || !['success', 'timeout', 'connection_error', 'http_error'].includes(spot.spot_poll_status ?? '')
    || !['valid_temperature', 'verified_no_target', 'empty_body', 'parse_error', 'invalid_sentinel', 'out_of_range', 'not_received', 'not_evaluated'].includes(spot.spot_raw_validity ?? '')
    || (spot.spot_value_age_ms != null && !isNonNegativeNumber(spot.spot_value_age_ms))
    || (spot.spot_cache_expiry_threshold_sec !== undefined
      && (!isNonNegativeNumber(spot.spot_cache_expiry_threshold_sec) || spot.spot_cache_expiry_threshold_sec <= 0))) {
    return unknown();
  }
  const stale = spot.spot_source_freshness === 'stale' || snapshotAgeMs > Math.max(5000, thresholdMs);
  const cached = spot.temperature_value_origin === 'cached_observation'
    && spot.cache_fallback_allowed === true && spot.spot_cache_status === 'reused';
  const cacheTtlMs = isNonNegativeNumber(spot.spot_cache_expiry_threshold_sec)
    ? spot.spot_cache_expiry_threshold_sec * 1000 : null;
  if (cached && (valueAgeMs === null || cacheTtlMs === null)) return unknown();
  const usableCache = cached && valueAgeMs !== null && cacheTtlMs !== null && valueAgeMs <= cacheTtlMs;
  if (spot.spot_poll_status !== 'success') {
    const temperature = usableCache ? 'CACHED'
      : stale || cached || spot.temperature_status_shadow === 'stale' ? 'STALE' : 'SOURCE_ERROR';
    return result('DOWN', temperature, 'error', temperature === 'SOURCE_ERROR' ? 'error' : 'warn');
  }
  if (stale) return result('STALE', usableCache ? 'CACHED' : 'STALE', 'warn', 'warn');
  if (cached) return result('OK', usableCache ? 'CACHED' : 'STALE', 'ok', 'warn');
  if (spot.spot_raw_validity === 'valid_temperature') {
    return spot.temperature_value_origin === 'current_observation'
      ? result('OK', 'OK', 'ok', 'ok') : unknown();
  }
  if (spot.spot_raw_validity === 'verified_no_target') return result('OK', 'NO_TARGET', 'ok', 'warn');
  if (spot.spot_raw_validity === 'invalid_sentinel') {
    if (spot.spot_device_status_code === 'temperature_under_range') return result('OK', 'UNDER_RANGE', 'ok', 'warn');
    if (spot.spot_device_status_code === 'temperature_over_range') return result('OK', 'OVER_RANGE', 'ok', 'warn');
  }
  return result('OK', 'INVALID', 'ok', 'warn');
};

export const getCameraStatus = (params: {
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotImageMetadata?: SpotImageResponseMetadata | null;
}): CameraStatus | null => {
  const { spotConfig, spotImageUrl, spotImageLoading, spotImageError, spotLastSuccessAt } = params;
  if (!spotConfig) {
    return null;
  }

  const parsedErrorStatus = spotImageError ? parseCameraStatusMessage(spotImageError) : null;

  if (parsedErrorStatus) {
    return parsedErrorStatus;
  }
  if (!spotImageUrl || spotImageLoading || spotLastSuccessAt === null) {
    return { type: 'loading' as const, title: '카메라 연결 중', detail: '' };
  }
  return null;
};
