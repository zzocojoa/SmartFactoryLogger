import { getCameraStatus } from './commBadge';
import type { SpotConfig } from '../types';

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
      spotImageError: '이미지 상태 지연\n캐시 stale · 프록시 ok',
      spotLastSuccessAt: 10_000,
    });

    expect(status).not.toBeNull();
    expect(status?.type).toBe('warn');
    expect(status?.title).toBe('이미지 상태 지연');
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
