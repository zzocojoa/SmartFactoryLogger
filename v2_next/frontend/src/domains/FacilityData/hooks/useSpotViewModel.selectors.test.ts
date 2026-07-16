import { describe, expect, it } from 'vitest';
import {
  resolveSpotImageErrorMessage,
  resolveSpotImageResponseMetadata,
  resolveSpotImageSuccessAt,
} from './useSpotViewModel.selectors';

describe('SPOT image response selectors', () => {
  it('reads image observability and cached internal-temperature headers', () => {
    const headers = new Headers({
      'X-Spot-Image-Source': 'upstream',
      'X-Spot-Image-At': '1700000004000',
      'X-Spot-Internal-Temperature': '41.250',
      'X-Spot-Internal-Temperature-At': '1700000003500',
      'X-Spot-Internal-Temperature-Status': 'ok',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 1_700_000_005_000, 25);

    expect(metadata).toEqual({
      source: 'upstream',
      captured_at: 1_700_000_004_000,
      internal_temperature: 41.25,
      internal_temperature_at: 1_700_000_003_500,
      internal_temperature_status: 'ok',
      received_at: 1_700_000_005_000,
      latency_ms: 25,
    });
    expect(resolveSpotImageSuccessAt(metadata, metadata.received_at)).toBe(1_700_000_004_000);
  });

  it('uses receive time when the bridge capture header is absent', () => {
    const metadata = resolveSpotImageResponseMetadata(new Headers(), 1_700_000_005_000, 10);
    expect(resolveSpotImageSuccessAt(metadata, metadata.received_at)).toBe(metadata.received_at);
    expect(metadata.internal_temperature).toBeNull();
    expect(metadata.internal_temperature_at).toBeNull();
    expect(metadata.internal_temperature_status).toBeNull();
  });

  it('maps upstream failures without cache or backoff states', () => {
    expect(resolveSpotImageErrorMessage(502, { code: 'upstream-timeout' })).toContain('초과');
    expect(
      resolveSpotImageErrorMessage(502, { code: 'upstream-http-error', upstream_status: 503 })
    ).toContain('503');
    expect(resolveSpotImageErrorMessage(404, { code: 'config-missing' })).toContain('IP');
  });
});
