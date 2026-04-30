import {
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
});
