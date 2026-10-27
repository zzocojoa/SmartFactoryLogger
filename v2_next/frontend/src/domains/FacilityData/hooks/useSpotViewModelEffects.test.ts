import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useRef } from 'react';
import type { SpotConfig } from '../../../shared/types';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';
import { useSpotViewModel } from './useSpotViewModel';

const service = vi.hoisted(() => ({
  config: vi.fn<() => Promise<SpotConfig>>(),
  image: vi.fn<() => Promise<Response>>(),
}));

vi.mock('./useSpotViewModel.service', () => ({
  fetchSpotConfig: () => service.config(),
  fetchSpotImageResponse: () => service.image(),
  controlSpotAction: vi.fn(),
  controlSpotFocus: vi.fn(),
  controlSpotActuator: vi.fn(),
}));

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
    vi.useRealTimers();
    service.config.mockReset();
    service.image.mockReset();
    vi.restoreAllMocks();
    window.localStorage.clear();
    setVisibilityState('visible');
  });

  it('rechecks storage pressure without spending or resetting ordinary retry attempts', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const failure = () => new Response(JSON.stringify({ detail: { code: 'upstream-timeout' } }), { status: 502 });
    const pressure = () => new Response(JSON.stringify({ detail: { code: 'storage_pressure' } }), {
      status: 503,
      headers: {
        'X-Spot-Image-Upstream-Suppressed': '1',
        'X-Spot-Image-Suppression-Reason': 'storage_pressure',
        'Retry-After': '2',
      },
    });
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockResolvedValueOnce(failure()).mockImplementation(async () => pressure());
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      expect(result.current.diagnostics.error_count).toBe(1);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(500); });
      expect(service.image).toHaveBeenCalledTimes(2);
      expect(result.current.diagnostics.error_count).toBe(1);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
      for (let retry = 0; retry < 4; retry += 1) {
        await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
        expect(service.image).toHaveBeenCalledTimes(2 + retry);
        await act(async () => { await vi.advanceTimersByTimeAsync(1); });
        expect(service.image).toHaveBeenCalledTimes(3 + retry);
        expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
      }
      service.image.mockResolvedValueOnce(failure());
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(result.current.diagnostics.error_count).toBe(2);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(2);
      const beforeRetry = service.image.mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(999); });
      expect(service.image).toHaveBeenCalledTimes(beforeRetry);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(service.image).toHaveBeenCalledTimes(beforeRetry + 1);
    } finally { unmount(); }
  });

  it('cancels pending retry and normal refresh while hidden, then resumes once when visible', async () => {
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
    expect(cancelPendingImageRetry).toHaveBeenCalledTimes(1);
    expect(cancelNormalImageRefresh).toHaveBeenCalledTimes(1);
    expect(resumeImageRefreshWhenVisible).not.toHaveBeenCalled();

    act(() => {
      setVisibilityState('visible');
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(resumeImageRefreshWhenVisible).toHaveBeenCalledTimes(1);

    unmount();
    expect(cancelPendingImageRetry).toHaveBeenCalledTimes(2);
    expect(cancelNormalImageRefresh).toHaveBeenCalledTimes(2);
  });
});
