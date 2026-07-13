import { describe, expect, it } from 'vitest';
import {
  SPOT_IMAGE_AUTO_RETRY_DELAYS_MS,
  getNextSpotImageRetryDelayMs,
  isSpotImageFailureRetryable,
} from './spotImageRecoveryPolicy.pure';

describe('SPOT image recovery policy', () => {
  it.each([
    { code: 'upstream-timeout' },
    { code: 'upstream-request-error' },
    { code: 'empty-body' },
    { code: 'upstream-http-error', upstreamStatus: 503 },
    { responseStatus: 502, code: 'upstream-http-error' },
    { responseStatus: 502 },
    { transportException: true },
    { displayFailure: true },
  ])('classifies transient failure as retryable: %o', (input) => {
    expect(isSpotImageFailureRetryable(input)).toBe(true);
  });

  it.each([
    { responseStatus: 404, code: 'config-missing' },
    { responseStatus: 502, code: 'invalid-image-html', payloadRejected: true },
    { responseStatus: 502, code: 'invalid-image-payload', payloadRejected: true },
    { responseStatus: 502, code: 'backend-payload-rejection', payloadRejected: true },
    { responseStatus: 502, code: 'upstream-http-error', upstreamStatus: 400 },
  ])('classifies persistent failure as terminal: %o', (input) => {
    expect(isSpotImageFailureRetryable(input)).toBe(false);
  });

  it('provides three bounded delays and then exhausts the retry budget', () => {
    expect(SPOT_IMAGE_AUTO_RETRY_DELAYS_MS).toEqual([500, 1_000, 2_000]);
    expect(getNextSpotImageRetryDelayMs(0)).toBe(500);
    expect(getNextSpotImageRetryDelayMs(1)).toBe(1_000);
    expect(getNextSpotImageRetryDelayMs(2)).toBe(2_000);
    expect(getNextSpotImageRetryDelayMs(3)).toBeNull();
    expect(getNextSpotImageRetryDelayMs(-1)).toBeNull();
  });

  it('does not treat non-HTTP status values above 599 as retryable', () => {
    expect(isSpotImageFailureRetryable({ responseStatus: 999 })).toBe(false);
  });
});
