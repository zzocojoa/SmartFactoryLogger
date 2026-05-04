import { getCameraStatus } from './commBadge';
import type { SpotConfig } from '../types';
import type { SpotImageResponseMetadata } from '../../domains/FacilityData/api/spotService.types';

describe('getCameraStatus', () => {
  const originalDateNow: () => number = Date.now;
  const config: SpotConfig = {
    image_url: 'http://spot.local/image.jpg',
    refresh_interval: 1,
    crosshair_x: 0.5,
    crosshair_y: 0.5,
    crosshair_color: 'lime',
    crosshair_thickness: 2,
    crosshair_size: 20,
    crosshair_gap: 5,
    widget_width: 512,
    widget_height: 288,
    focus_step: 5,
    focus_enabled: true,
  };
  const metadata: SpotImageResponseMetadata = {
    status: 'ok',
    raw_status: 'ok',
    cache_status: 'fresh',
    raw_cache_status: 'fresh',
    proxy_state: 'ok',
    raw_proxy_state: 'ok',
    source: 'cache',
    age_sec: 0.25,
    max_stale_age_sec: 5,
    captured_at: 9_750,
    retry_after_sec: null,
    received_at: 10_000,
    latency_ms: 12,
  };

  beforeEach(() => {
    Date.now = jest.fn((): number => 10_000);
  });

  afterEach(() => {
    Date.now = originalDateNow;
  });

  it('returns null before the refresh interval warn threshold', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 6_000,
    });

    expect(status).toBeNull();
  });

  it('returns warn after the refresh interval warn threshold', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 5_999,
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('warn');
    expect(status?.title).toBe('이미지 수신 지연');
  });

  it('returns danger after the stale image threshold', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 4_999,
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('danger');
    expect(status?.title).toBe('카메라 응답 지연');
  });

  it('uses image age metadata before response success time', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 10_000,
      spotImageMetadata: {
        ...metadata,
        age_sec: 5.1,
      },
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('danger');
    expect(status?.title).toBe('오래된 이미지 제공 중');
    expect(status?.detail).toBe('이미지 나이 5초');
  });

  it('returns warn for image age metadata before the danger threshold', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 10_000,
      spotImageMetadata: {
        ...metadata,
        age_sec: 4.1,
      },
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('warn');
    expect(status?.title).toBe('이미지 오래됨');
    expect(status?.detail).toBe('이미지 나이 4초');
  });

  it('uses captured_at when image age is missing', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 10_000,
      spotImageMetadata: {
        ...metadata,
        age_sec: null,
        captured_at: 4_900,
      },
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('danger');
    expect(status?.title).toBe('오래된 이미지 제공 중');
    expect(status?.detail).toBe('이미지 나이 5초');
  });

  it('applies age severity before stale diagnostic text', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: '오래된 이미지 제공 중\n캐시 stale · 프록시 ok',
      spotLastSuccessAt: 10_000,
      spotImageMetadata: {
        ...metadata,
        age_sec: 5.1,
      },
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('danger');
    expect(status?.title).toBe('오래된 이미지 제공 중');
    expect(status?.detail).toBe('이미지 나이 5초');
  });

  it('keeps fresh image metadata normal even when the previous receive time is old', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: null,
      spotLastSuccessAt: 4_999,
      spotImageMetadata: metadata,
    });

    expect(status).toBeNull();
  });

  it('returns warn for SPOT proxy backoff diagnostics', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: '이미지 요청 대기\n상태 backoff · 재시도 1.5초',
      spotLastSuccessAt: 10_000,
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('warn');
    expect(status?.title).toBe('이미지 요청 대기');
    expect(status?.detail).toBe('상태 backoff · 재시도 1.5초');
  });

  it('returns warn for SPOT stale cache diagnostics', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: '오래된 이미지 제공 중\n캐시 stale · 프록시 ok',
      spotLastSuccessAt: 10_000,
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('warn');
    expect(status?.title).toBe('오래된 이미지 제공 중');
    expect(status?.detail).toBe('캐시 stale · 프록시 ok');
  });

  it('keeps non-diagnostic camera errors as errors', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'http://localhost/api/spot/proxy_image',
      spotImageLoading: false,
      spotImageError: '이미지 프록시 오류\n상태 error',
      spotLastSuccessAt: 10_000,
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('error');
    expect(status?.title).toBe('이미지 프록시 오류');
    expect(status?.detail).toBe('상태 error');
  });
});
