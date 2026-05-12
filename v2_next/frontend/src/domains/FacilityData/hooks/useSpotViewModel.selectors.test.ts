import { describe, expect, it } from 'vitest';
import {
  resolveSpotImageDiagnosticMessage,
  resolveSpotImageResponseMetadata,
  resolveSpotImageSuccessAt,
} from './useSpotViewModel.selectors';

describe('resolveSpotImageResponseMetadata', () => {
  it('uses proxy backoff as the effective status even when cached image is fresh', () => {
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'fresh',
      'X-Spot-Proxy-State': 'backoff',
      'X-Spot-Image-Source': 'cache',
      'X-Spot-Image-Age': '0.25',
      'Retry-After': '9',
      'X-Spot-Retry-After-Ms': '1500',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 10_000, 24);

    expect(metadata.status).toBe('backoff');
    expect(metadata.cache_status).toBe('fresh');
    expect(metadata.proxy_state).toBe('backoff');
    expect(metadata.raw_cache_status).toBe('fresh');
    expect(metadata.raw_proxy_state).toBe('backoff');
    expect(metadata.retry_after_sec).toBe(1.5);
    expect(resolveSpotImageSuccessAt(metadata, 10_000)).toBe(10_000);
    expect(resolveSpotImageDiagnosticMessage(metadata)).toBeNull();
  });

  it('treats stale cache status as the effective status', () => {
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'stale',
      'X-Spot-Proxy-State': 'ok',
      'X-Spot-Image-Source': 'stale',
      'X-Spot-Image-Age': '7.5',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 20_000, 18);

    expect(metadata.status).toBe('stale');
    expect(metadata.cache_status).toBe('stale');
    expect(resolveSpotImageSuccessAt(metadata, 20_000)).toBe(12_500);
  });

  it('uses proxy error as the effective status even when cached image is fresh', () => {
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'fresh',
      'X-Spot-Proxy-State': 'error',
      'X-Spot-Image-Source': 'cache',
      'X-Spot-Image-Age': '0.5',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 30_000, 32);

    expect(metadata.status).toBe('error');
    expect(metadata.cache_status).toBe('fresh');
    expect(metadata.proxy_state).toBe('error');
    expect(resolveSpotImageSuccessAt(metadata, 30_000)).toBe(30_000);
    expect(resolveSpotImageDiagnosticMessage(metadata)).toBeNull();
  });

  it('normalizes X-Spot-Image-Age from milliseconds', () => {
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'stale',
      'X-Spot-Proxy-State': 'ok',
      'X-Spot-Image-Age': '15000',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 40_000, 18);

    expect(metadata.age_sec).toBe(15);
    expect(resolveSpotImageSuccessAt(metadata, 40_000)).toBe(25_000);
  });

  it('normalizes X-Spot-Image-At from seconds to milliseconds', () => {
    const capturedAtSeconds = 1_700_000_004;
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'stale',
      'X-Spot-Proxy-State': 'ok',
      'X-Spot-Image-At': String(capturedAtSeconds),
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 40_000, 18);

    expect(metadata.captured_at).toBe(capturedAtSeconds * 1000);
    expect(resolveSpotImageSuccessAt(metadata, 40_000)).toBe(capturedAtSeconds * 1000);
  });

  it('ignores non-finite retry headers', () => {
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'fresh',
      'X-Spot-Proxy-State': 'ok',
      'Retry-After': 'Infinity',
      'X-Spot-Retry-After-Ms': 'NaN',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 40_000, 12);

    expect(metadata.retry_after_sec).toBeNull();
  });

  it('parses SPOT internal temperature headers', () => {
    const headers = new Headers({
      'X-Spot-Image-Status': 'ok',
      'X-Spot-Cache-Status': 'fresh',
      'X-Spot-Proxy-State': 'ok',
      'X-Spot-Internal-Temperature': '41.2',
      'X-Spot-Internal-Temperature-At': '1700000004',
      'X-Spot-Internal-Temperature-Status': 'ok',
    });

    const metadata = resolveSpotImageResponseMetadata(headers, 40_000, 12);

    expect(metadata.internal_temperature).toBe(41.2);
    expect(metadata.internal_temperature_at).toBe(1_700_000_004_000);
    expect(metadata.internal_temperature_status).toBe('ok');
  });
});
