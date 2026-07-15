export interface SpotImageFailureClassificationInput {
  responseStatus?: number | null;
  code?: string | null;
  upstreamStatus?: number | null;
  payloadRejected?: boolean;
  transportException?: boolean;
  displayFailure?: boolean;
}

export const SPOT_IMAGE_AUTO_RETRY_DELAYS_MS = [500, 1_000, 2_000] as const;

const TRANSIENT_CODES = new Set([
  'empty-body',
  'upstream-request-error',
  'upstream-timeout',
]);

const PERSISTENT_CODES = new Set([
  'backend-payload-rejection',
  'config-missing',
  'invalid-image-html',
  'invalid-image-payload',
]);

const isRetryableHttpStatus = (status: number | null | undefined): boolean => {
  if (status === null || status === undefined || !Number.isInteger(status)) {
    return false;
  }
  return status === 408 || status === 425 || status === 429 || (status >= 500 && status <= 599);
};

export const isSpotImageFailureRetryable = ({
  responseStatus,
  code,
  upstreamStatus,
  payloadRejected = false,
  transportException = false,
  displayFailure = false,
}: SpotImageFailureClassificationInput): boolean => {
  if (transportException || displayFailure) {
    return true;
  }
  if (payloadRejected) {
    return false;
  }

  const normalizedCode = String(code ?? '').trim().toLowerCase();
  if (PERSISTENT_CODES.has(normalizedCode)) {
    return false;
  }
  if (TRANSIENT_CODES.has(normalizedCode)) {
    return true;
  }
  if (normalizedCode === 'upstream-http-error') {
    return isRetryableHttpStatus(upstreamStatus ?? responseStatus);
  }
  return isRetryableHttpStatus(responseStatus);
};

export const getNextSpotImageRetryDelayMs = (
  attemptsAlreadyScheduled: number
): number | null => {
  if (!Number.isInteger(attemptsAlreadyScheduled) || attemptsAlreadyScheduled < 0) {
    return null;
  }
  return SPOT_IMAGE_AUTO_RETRY_DELAYS_MS[attemptsAlreadyScheduled] ?? null;
};
