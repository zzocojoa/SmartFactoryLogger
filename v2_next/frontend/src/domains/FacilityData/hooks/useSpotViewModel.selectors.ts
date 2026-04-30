import type {
  SpotImageHeaderStatus,
  SpotImageResponseMetadata,
} from '../api/spotService.types';

export type SpotProxyDiagnostics = {
  cache_state?: string | null;
  failure_count?: number | null;
  last_error_at?: number | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  image_url_configured?: boolean | null;
};

export type SpotProxyErrorDetail = {
  code?: string | null;
  message?: string | null;
  upstream_status?: number | null;
  image_url?: string | null;
  diagnostics?: SpotProxyDiagnostics | null;
};

export const resolveSpotRefreshMs = (refreshIntervalSec: number): number => {
  return Math.max(500, Math.round(refreshIntervalSec * 1000));
};

const normalizeSpotImageStatus = (rawStatus: string | null): SpotImageHeaderStatus => {
  const normalizedStatus = String(rawStatus ?? '').trim().toLowerCase();
  if (
    normalizedStatus === 'ok' ||
    normalizedStatus === 'fresh' ||
    normalizedStatus === 'stale' ||
    normalizedStatus === 'backoff' ||
    normalizedStatus === 'error' ||
    normalizedStatus === 'empty'
  ) {
    return normalizedStatus;
  }
  return 'unknown';
};

const parseFiniteNumber = (rawValue: string | null): number | null => {
  if (rawValue === null) {
    return null;
  }
  const normalizedValue = rawValue.trim();
  if (normalizedValue === '') {
    return null;
  }
  const parsedValue = Number(normalizedValue);
  return Number.isFinite(parsedValue) ? parsedValue : null;
};

const parseRetryAfterSec = (
  rawValue: string | null,
  rawMilliseconds: string | null,
  receivedAt: number
): number | null => {
  const millisecondsValue = parseFiniteNumber(rawMilliseconds);
  if (millisecondsValue !== null) {
    return Math.max(0, millisecondsValue / 1000);
  }

  const numericValue = parseFiniteNumber(rawValue);
  if (numericValue !== null) {
    return Math.max(0, numericValue);
  }
  if (rawValue === null) {
    return null;
  }
  const retryAt = Date.parse(rawValue);
  if (!Number.isFinite(retryAt)) {
    return null;
  }
  return Math.max(0, (retryAt - receivedAt) / 1000);
};

const resolveEffectiveSpotHeaderStatus = (
  imageStatus: SpotImageHeaderStatus,
  cacheStatus: SpotImageHeaderStatus,
  proxyState: SpotImageHeaderStatus
): SpotImageHeaderStatus => {
  if (proxyState === 'backoff' || proxyState === 'error') {
    return proxyState;
  }
  if (cacheStatus === 'fresh') {
    return 'ok';
  }
  if (cacheStatus === 'stale') {
    return 'stale';
  }
  if (imageStatus === 'ok' || imageStatus === 'fresh') {
    return 'ok';
  }
  if (imageStatus === 'stale') {
    return 'stale';
  }
  if (imageStatus === 'empty' || cacheStatus === 'empty') {
    return 'empty';
  }
  return imageStatus;
};

const formatSpotMetadataDetail = (metadata: SpotImageResponseMetadata): string => {
  const parts: string[] = [
    `상태 ${metadata.raw_status ?? metadata.status}`,
    `캐시 ${metadata.raw_cache_status ?? metadata.cache_status}`,
    `프록시 ${metadata.raw_proxy_state ?? metadata.proxy_state}`,
    `원본 ${metadata.source ?? '--'}`,
    `나이 ${metadata.age_sec === null ? '--' : `${metadata.age_sec.toFixed(2)}초`}`,
    `응답 ${Math.round(metadata.latency_ms)}ms`,
  ];
  if (metadata.retry_after_sec !== null) {
    parts.push(`재시도 ${metadata.retry_after_sec.toFixed(1)}초`);
  }
  return parts.join(' · ');
};

export const resolveSpotImageResponseMetadata = (
  headers: Headers,
  receivedAt: number,
  latencyMs: number
): SpotImageResponseMetadata => {
  const rawStatus = headers.get('X-Spot-Image-Status');
  const rawCacheStatus = headers.get('X-Spot-Cache-Status');
  const rawProxyState = headers.get('X-Spot-Proxy-State');
  const imageStatus = normalizeSpotImageStatus(rawStatus);
  const cacheStatus = normalizeSpotImageStatus(rawCacheStatus);
  const proxyState = normalizeSpotImageStatus(rawProxyState);
  const source = headers.get('X-Spot-Image-Source');
  return {
    status: resolveEffectiveSpotHeaderStatus(imageStatus, cacheStatus, proxyState),
    raw_status: rawStatus,
    cache_status: cacheStatus,
    raw_cache_status: rawCacheStatus,
    proxy_state: proxyState,
    raw_proxy_state: rawProxyState,
    source,
    age_sec: parseFiniteNumber(headers.get('X-Spot-Image-Age')),
    max_stale_age_sec: parseFiniteNumber(headers.get('X-Spot-Max-Stale-Age')),
    captured_at: parseFiniteNumber(headers.get('X-Spot-Image-At')),
    retry_after_sec: parseRetryAfterSec(headers.get('Retry-After'), headers.get('X-Spot-Retry-After-Ms'), receivedAt),
    received_at: receivedAt,
    latency_ms: latencyMs,
  };
};

export const resolveSpotImageDiagnosticMessage = (
  metadata: SpotImageResponseMetadata
): string | null => {
  if (metadata.status === 'stale') {
    return `이미지 상태 지연\n${formatSpotMetadataDetail(metadata)}`;
  }
  if (metadata.status === 'backoff') {
    return `이미지 요청 대기\n${formatSpotMetadataDetail(metadata)}`;
  }
  if (metadata.status === 'error') {
    return `이미지 프록시 오류\n${formatSpotMetadataDetail(metadata)}`;
  }
  return null;
};

export const resolveSpotImageSuccessAt = (
  metadata: SpotImageResponseMetadata,
  receivedAt: number
): number => {
  if (
    metadata.status === 'ok' ||
    metadata.status === 'fresh' ||
    metadata.cache_status === 'fresh'
  ) {
    return receivedAt;
  }
  if (metadata.age_sec !== null) {
    return receivedAt - Math.max(0, metadata.age_sec * 1000);
  }
  if (metadata.captured_at !== null) {
    return metadata.captured_at;
  }
  return receivedAt;
};

export const resolveSpotImageErrorMessage = (
  status: number,
  detail: SpotProxyErrorDetail | null
): string => {
  const code = String(detail?.code ?? '').trim();

  if (status === 404 || code === 'config-missing') {
    return '이미지 URL 미설정';
  }
  if (code === 'empty-body') {
    return '이미지 응답 비어 있음';
  }
  if (code === 'upstream-timeout') {
    return '이미지 응답 시간 초과';
  }
  if (code === 'upstream-http-error') {
    const upstreamStatus = detail?.upstream_status;
    return upstreamStatus ? `이미지 서버 HTTP ${upstreamStatus}` : '이미지 서버 HTTP 오류';
  }
  if (code === 'upstream-request-error') {
    return '이미지 서버 연결 실패';
  }
  if (status === 502) {
    return '이미지 수신 실패';
  }
  return '이미지 요청 실패';
};

export const resolveSpotImageLoadErrorMessage = (): string => {
  return '이미지 로드 실패';
};

export const resolveEffectiveSpotImageAt = (
  capturedAtHeader: string | null,
  ageHeader: string | null,
  receivedAt: number
): number => {
  const capturedAt = capturedAtHeader ? Number(capturedAtHeader) : NaN;
  const ageSec = ageHeader ? Number(ageHeader) : NaN;
  if (Number.isFinite(ageSec)) {
    return receivedAt - Math.max(0, ageSec * 1000);
  }
  if (Number.isFinite(capturedAt)) {
    return capturedAt;
  }
  return receivedAt;
};
