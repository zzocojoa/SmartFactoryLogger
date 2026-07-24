import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useRef } from 'react';
import type { SpotConfig } from '../../../shared/types';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';

vi.mock('../../../shared/utils/dashboardPollingLeader', () => ({
  clearDashboardLeaderLock: vi.fn(),
  readDashboardLeaderLock: vi.fn(() => null),
  readOrCreateDashboardTabId: vi.fn(() => 'test-tab'),
  writeDashboardLeaderLock: vi.fn(),
}));

const SPOT_CONFIG: SpotConfig = {
  image_url: '/api/spot/image.jpg',
  refresh_interval: 3,
  crosshair_x: 0.5,
  crosshair_y: 0.5,
  crosshair_color: '#ffffff',
  crosshair_thickness: 2,
  crosshair_size: 80,
  crosshair_gap: 6,
  widget_width: 320,
  widget_height: 240,
  focus_step: 10,
  actuator_step: 5,
  focus_enabled: true,
};

const setVisibilityState = (state: DocumentVisibilityState): void => {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: state,
  });
};

describe('useSpotViewModelEffects image lifecycle', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    setVisibilityState('visible');
  });

  it('cancels normal refresh while hidden and resumes once when visible', async () => {
    setVisibilityState('visible');
    const fetchInitialImage = vi.fn(async () => undefined);
    const loadConfig = vi.fn(async () => null);
    const applySpotConfig = vi.fn();
    const cancelPendingImageRetry = vi.fn();
    const cancelNormalImageRefresh = vi.fn();
    const resumeImageRefreshWhenVisible = vi.fn();

    const { unmount } = renderHook(() => {
      const prevUrlRef = useRef<string | null>(null);
      useSpotViewModelEffects({
        config: SPOT_CONFIG,
        fetchInitialImage,
        loadConfig,
        applySpotConfig,
        prevUrlRef,
        cancelPendingImageRetry,
        cancelNormalImageRefresh,
        resumeImageRefreshWhenVisible,
      });
    });

    expect(fetchInitialImage).toHaveBeenCalledTimes(1);

    act(() => {
      setVisibilityState('hidden');
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(cancelNormalImageRefresh).toHaveBeenCalledTimes(1);
    expect(resumeImageRefreshWhenVisible).not.toHaveBeenCalled();

    act(() => {
      setVisibilityState('visible');
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(resumeImageRefreshWhenVisible).toHaveBeenCalledTimes(1);

    unmount();
    expect(cancelPendingImageRetry).toHaveBeenCalledTimes(1);
    expect(cancelNormalImageRefresh).toHaveBeenCalledTimes(2);
  });
});
