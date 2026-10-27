import { describe, expect, it } from 'vitest';
import {
  resolveSpotImageErrorMessage,
  resolveSpotImageResponseMetadata,
  resolveSpotImageSuccessAt,
} from './useSpotViewModel.selectors';

describe('SPOT image response selectors', () => {
  it('parses explicit storage suppression and integer retry seconds without inventing legacy state', () => {
    const resolve = (values: Record<string, string>) =>
      resolveSpotImageResponseMetadata(new Headers(values), 1_700_000_005_000, 25);
    expect(resolve({})).toMatchObject({
      image_upstream_suppressed: null, suppression_reason: null, retry_after_sec: null,
    });
    expect(resolve({
      'X-Spot-Image-Upstream-Suppressed': 'garbage',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '3',
    })).toMatchObject({ image_upstream_suppressed: null, suppression_reason: null, retry_after_sec: null });
    for (const retry of ['0', '-1', '1.5', 'Infinity', '1e3', '9007199254740992', 'Wed, 21 Oct 2026 07:28:00 GMT']) {
      expect(resolve({
        'X-Spot-Image-Upstream-Suppressed': '1',
        'X-Spot-Image-Suppression-Reason': 'storage_pressure',
        'Retry-After': retry,
      })).toMatchObject({ image_upstream_suppressed: true, suppression_reason: 'storage_pressure', retry_after_sec: null });
    }
    expect(resolve({
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '3',
    })).toMatchObject({ image_upstream_suppressed: true, suppression_reason: 'storage_pressure', retry_after_sec: 3 });
    expect(resolve({
      'X-Spot-Image-Upstream-Suppressed': '0',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '3',
    })).toMatchObject({ image_upstream_suppressed: false, suppression_reason: null, retry_after_sec: null });
    expect(resolve({
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'other',
      'Retry-After': '3',
    })).toMatchObject({ image_upstream_suppressed: true, suppression_reason: null, retry_after_sec: null });
  });

  it('reads image observability and cached internal-temperature headers', () => {
    const headers = new Headers({
      'X-Spot-Image-Source': 'upstream',
      'X-Spot-Image-At': '1700000004000',
      'X-Spot-Image-Age-Ms': '250.5',
      'X-Spot-Internal-Temperature': '41.250',
      'X-Spot-Internal-Temperature-At': '1700000003500',
      'X-Spot-Internal-Temperature-Status': 'ok',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 1_700_000_005_000, 25);

    expect(metadata).toEqual({
      image_upstream_suppressed: null,
      suppression_reason: null,
      retry_after_sec: null,
      source: 'upstream',
      captured_at: 1_700_000_004_000,
      age_ms: 250.5,
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
    expect(metadata.age_ms).toBeNull();
  });

  it('maps upstream failures without cache or backoff states', () => {
    expect(resolveSpotImageErrorMessage(502, { code: 'upstream-timeout' })).toContain('초과');
    expect(
      resolveSpotImageErrorMessage(502, { code: 'upstream-http-error', upstream_status: 503 })
    ).toContain('503');
    expect(resolveSpotImageErrorMessage(404, { code: 'config-missing' })).toContain('IP');
  });
});
