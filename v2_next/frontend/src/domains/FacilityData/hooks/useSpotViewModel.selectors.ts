import type { SpotImageResponseMetadata } from '../api/spotService.types';
import { normalizeSpotImageCapturedAt } from '../utils/spotImageMetadataNormalization.pure';

export type SpotImageDiagnostics = {
  failure_count?: number | null;
  last_error_at?: number | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  image_url_configured?: boolean | null;
};

export type SpotImageErrorDetail = {
  code?: string | null;
  message?: string | null;
  upstream_status?: number | null;
  image_url?: string | null;
  diagnostics?: SpotImageDiagnostics | null;
};

const parseFiniteNumber = (rawValue: string | null): number | null => {
  const normalized = rawValue?.trim() ?? '';
  if (normalized === '') {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
};

export const resolveSpotImageResponseMetadata = (
  headers: Headers,
  receivedAt: number,
  latencyMs: number
): SpotImageResponseMetadata => ({
  source: headers.get('X-Spot-Image-Source'),
  captured_at: normalizeSpotImageCapturedAt(headers.get('X-Spot-Image-At')),
  age_ms: parseFiniteNumber(headers.get('X-Spot-Image-Age-Ms')),
  internal_temperature: parseFiniteNumber(headers.get('X-Spot-Internal-Temperature')),
  internal_temperature_at: normalizeSpotImageCapturedAt(
    headers.get('X-Spot-Internal-Temperature-At')
  ),
  internal_temperature_status: headers.get('X-Spot-Internal-Temperature-Status'),
  received_at: receivedAt,
  latency_ms: latencyMs,
});

export const resolveSpotImageSuccessAt = (
  metadata: SpotImageResponseMetadata,
  receivedAt: number
): number => metadata.captured_at ?? receivedAt;

export const resolveSpotImageErrorMessage = (
  status: number,
  detail: SpotImageErrorDetail | null
): string => {
  const code = String(detail?.code ?? '').trim();

  if (status === 404 || code === 'config-missing') {
    return 'SPOT IP가 설정되지 않았습니다.';
  }
  if (code === 'empty-body') {
    return 'SPOT 이미지 응답이 비어 있습니다.';
  }
  if (code === 'upstream-timeout') {
    return 'SPOT 이미지 응답 시간이 초과되었습니다.';
  }
  if (code === 'upstream-http-error') {
    const upstreamStatus = detail?.upstream_status;
    return upstreamStatus
      ? `SPOT 이미지 서버 HTTP ${upstreamStatus}`
      : 'SPOT 이미지 서버 HTTP 오류';
  }
  if (code === 'upstream-request-error') {
    return 'SPOT 이미지 서버 연결에 실패했습니다.';
  }
  if (status === 502) {
    return 'SPOT 이미지 수신에 실패했습니다.';
  }
  return 'SPOT 이미지 요청에 실패했습니다.';
};

export const resolveSpotImageLoadErrorMessage = (): string => {
  return 'SPOT 이미지 표시에 실패했습니다.';
};
