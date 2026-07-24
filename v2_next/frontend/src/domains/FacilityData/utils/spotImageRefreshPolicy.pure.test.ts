import { describe, expect, it } from 'vitest';
import {
  DEFAULT_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS,
  resolveSpotImageRefreshIntervalMs,
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
});
