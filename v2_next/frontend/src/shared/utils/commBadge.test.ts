import { describe, expect, it } from 'vitest';
import { getCameraStatus } from './commBadge';
import type { SpotConfig } from '../types';

const config: SpotConfig = {
  image_url: '/api/spot/image.jpg',
  refresh_interval: 3,
  crosshair_x: 0.5,
  crosshair_y: 0.5,
  crosshair_color: 'lime',
  crosshair_thickness: 2,
  crosshair_size: 20,
  crosshair_gap: 5,
  widget_width: 512,
  widget_height: 288,
  focus_step: 5,
  actuator_step: 5,
  focus_enabled: true,
};

describe('getCameraStatus', () => {
  it('shows loading until the first image is displayed', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: '',
      spotImageLoading: true,
      spotImageError: null,
      spotLastSuccessAt: null,
    });
    expect(status?.type).toBe('loading');
  });

  it('returns no overlay after a successful display', () => {
    expect(
      getCameraStatus({
        spotConfig: config,
        spotImageUrl: 'blob:spot-image',
        spotImageLoading: false,
        spotImageError: null,
        spotLastSuccessAt: Date.now(),
      })
    ).toBeNull();
  });

  it('shows the image error without cache or stale severity states', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'blob:previous-image',
      spotImageLoading: false,
      spotImageError: 'SPOT 이미지 표시에 실패했습니다.',
      spotLastSuccessAt: Date.now(),
    });
    expect(status?.type).toBe('error');
    expect(status?.title).toContain('실패');
  });

  it('returns null before SPOT config is available', () => {
    expect(
      getCameraStatus({
        spotConfig: null,
        spotImageUrl: '',
        spotImageLoading: false,
        spotImageError: null,
        spotLastSuccessAt: null,
      })
    ).toBeNull();
  });
});
