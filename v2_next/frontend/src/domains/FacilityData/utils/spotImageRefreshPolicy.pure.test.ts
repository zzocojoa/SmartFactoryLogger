import { describe, expect, it } from 'vitest';
import {
  DEFAULT_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS,
  MIN_SPOT_OPERATOR_IMAGE_REFRESH_INTERVAL_SECONDS,
  resolveSpotImageRefreshIntervalMs,
  resolveSpotOperatorImageRefreshIntervalMs,
  normalizeSpotImageRefreshIntervalSeconds,
} from './spotImageRefreshPolicy.pure';

describe('SPOT image refresh policy', () => {
  it.each([undefined, null, Number.NaN, Number.POSITIVE_INFINITY, 0, -1])(
    'uses the default for invalid interval %s',
    (configuredInterval) => {
      expect(normalizeSpotImageRefreshIntervalSeconds(configuredInterval)).toBe(
        DEFAULT_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS
      );
    }
  );

  it('clamps finite intervals to the supported one-to-ten-second range', () => {
    expect(normalizeSpotImageRefreshIntervalSeconds(0.5)).toBe(1);
    expect(normalizeSpotImageRefreshIntervalSeconds(4.25)).toBe(4.25);
    expect(normalizeSpotImageRefreshIntervalSeconds(11)).toBe(10);
  });

  it('returns the normalized interval in milliseconds', () => {
    expect(resolveSpotImageRefreshIntervalMs(2.5)).toBe(2_500);
    expect(resolveSpotImageRefreshIntervalMs('3')).toBe(3_000);
  });

  it('uses the server-derived operator cadence down to the 250ms safety floor', () => {
    expect(resolveSpotOperatorImageRefreshIntervalMs(0.25, 3)).toBe(250);
    expect(resolveSpotOperatorImageRefreshIntervalMs(0.1, 3)).toBe(
      MIN_SPOT_OPERATOR_IMAGE_REFRESH_INTERVAL_SECONDS * 1_000
    );
    expect(resolveSpotOperatorImageRefreshIntervalMs(0.833333, 3)).toBeCloseTo(833.333);
  });

  it.each([undefined, null, Number.NaN, Number.POSITIVE_INFINITY, 0, -1])(
    'falls back to the legacy configured interval for invalid operator cadence %s',
    (serverInterval) => {
      expect(resolveSpotOperatorImageRefreshIntervalMs(serverInterval, 2.5)).toBe(2_500);
    }
  );
});
