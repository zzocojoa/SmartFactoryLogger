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
