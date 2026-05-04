/**
 * 통신 상태 배지와 카메라 상태 유틸리티
 */
import type { SpotImageResponseMetadata } from '../../domains/FacilityData/api/spotService.types';
import type { CommChannelMetrics, CommSpotMetrics, SpotConfig } from '../types';
import { formatAgeSec, formatOptionalSeconds, formatTimeFromSec } from './formatters';

export type CommBadge = {
  key: string;
  text: string;
  title: string;
  state: 'ok' | 'warn' | 'error' | 'idle';
};

type CameraStatus = {
  type: 'error' | 'loading' | 'danger' | 'warn';
  title: string;
  detail: string;
};

const isImageAgeDiagnosticTitle = (title: string): boolean => {
  return title === '오래된 이미지 제공 중' || title === '이미지 상태 지연';
};

const parseCameraStatusMessage = (message: string): CameraStatus => {
  const [title, ...detailParts] = message.split('\n');
  const normalizedTitle = title.trim();
  const detail = detailParts.join(' ').trim();
  const type = normalizedTitle === '오래된 이미지 제공 중' ||
    normalizedTitle === '이미지 상태 지연' ||
    normalizedTitle === '이미지 요청 대기'
    ? 'warn'
    : 'error';
  return {
    type,
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

export const buildSpotCommBadge = (
  key: string,
  metrics?: CommSpotMetrics,
  nowMs?: number | null,
  refreshMs?: number | null
): CommBadge => {
  if (!metrics) {
    return { key, text: `${key} --`, title: `${key}: no data`, state: 'idle' };
  }

  const lastSuccess = metrics.last_success_time ?? null;
  const lastError = metrics.last_error_time ?? null;
  const readFailures = metrics.read_failures ?? 0;
  const ageMs = lastSuccess && nowMs ? Math.max(0, nowMs - lastSuccess * 1000) : null;
  const staleMs = Math.max(5000, Math.round((refreshMs ?? 1000) * 3));
  let state: CommBadge['state'] = 'idle';
  let label = 'IDLE';

  if (lastSuccess && ageMs !== null && ageMs <= staleMs) {
    state = 'ok';
    label = 'OK';
  } else if (lastSuccess && ageMs !== null && ageMs > staleMs) {
    state = 'warn';
    label = 'STALE';
  } else if (lastError || readFailures > 0) {
    state = 'error';
    label = 'DOWN';
  } else {
    state = 'warn';
    label = 'WAIT';
  }

  const titleParts = [
    `${key} ${label}`,
    `최근 성공 ${formatTimeFromSec(lastSuccess)}`,
    `최근 오류 ${formatTimeFromSec(lastError)}`,
    `오류 경과 ${formatAgeSec(lastError, nowMs ?? null)}`,
    `실패 ${readFailures}`,
  ];

  return {
    key,
    text: `${key} ${label}`,
    title: titleParts.join(' | '),
    state,
  };
};

export const getCameraStatus = (params: {
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotImageMetadata?: SpotImageResponseMetadata | null;
}): CameraStatus | null => {
  const { spotConfig, spotImageUrl, spotImageLoading, spotImageError, spotLastSuccessAt, spotImageMetadata } = params;
  if (!spotConfig) {
    return null;
  }

  const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
  const now = Date.now();
  const responseDelayMs = spotLastSuccessAt ? now - spotLastSuccessAt : null;
  const imageAgeMs = resolveSpotImageAgeMs(spotImageMetadata ?? null, now);
  const parsedErrorStatus = spotImageError ? parseCameraStatusMessage(spotImageError) : null;

  if (parsedErrorStatus && !isImageAgeDiagnosticTitle(parsedErrorStatus.title)) {
    return parsedErrorStatus;
  }
  if (!spotImageUrl || spotImageLoading || spotLastSuccessAt === null) {
    return { type: 'loading' as const, title: '카메라 연결 중', detail: '' };
  }
  if (imageAgeMs !== null && imageAgeMs > refreshMs * 5) {
    return {
      type: 'danger' as const,
      title: '오래된 이미지 제공 중',
      detail: `이미지 나이 ${Math.round(imageAgeMs / 1000)}초`,
    };
  }
  if (imageAgeMs !== null && imageAgeMs > refreshMs * 4) {
    return {
      type: 'warn' as const,
      title: '이미지 오래됨',
      detail: `이미지 나이 ${Math.round(imageAgeMs / 1000)}초`,
    };
  }
  if (parsedErrorStatus) {
    return parsedErrorStatus;
  }
  if (imageAgeMs !== null) {
    return null;
  }
  if (responseDelayMs !== null && responseDelayMs > refreshMs * 5) {
    return {
      type: 'danger' as const,
      title: '카메라 응답 지연',
      detail: `응답 지연 ${Math.round(responseDelayMs / 1000)}초`,
    };
  }
  if (responseDelayMs !== null && responseDelayMs > refreshMs * 4) {
    return {
      type: 'warn' as const,
      title: '이미지 수신 지연',
      detail: `응답 지연 ${Math.round(responseDelayMs / 1000)}초`,
    };
  }
  return null;
};

const resolveSpotImageAgeMs = (
  metadata: SpotImageResponseMetadata | null,
  nowMs: number
): number | null => {
  if (!metadata) {
    return null;
  }
  const elapsedSinceReceiveMs = Math.max(0, nowMs - metadata.received_at);
  if (metadata.age_sec !== null && Number.isFinite(metadata.age_sec)) {
    return Math.max(0, metadata.age_sec * 1000) + elapsedSinceReceiveMs;
  }
  if (metadata.captured_at !== null && Number.isFinite(metadata.captured_at)) {
    return Math.max(0, nowMs - metadata.captured_at);
  }
  return null;
};
