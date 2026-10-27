import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useRef } from 'react';
import type { SpotConfig } from '../../../shared/types';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';
import { useSpotViewModel } from './useSpotViewModel';

const service = vi.hoisted(() => ({
  config: vi.fn<() => Promise<SpotConfig>>(),
  image: vi.fn<(url: string) => Promise<Response>>(),
}));

vi.mock('./useSpotViewModel.service', () => ({
  fetchSpotConfig: () => service.config(),
  fetchSpotImageResponse: (url: string) => service.image(url),
  controlSpotAction: vi.fn(),
  controlSpotFocus: vi.fn(),
  controlSpotActuator: vi.fn(),
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

const imageResponse = (suppressed: boolean, retry = '2'): Response => new Response(
  new Uint8Array([0xff, 0xd8, ...Array<number>(16).fill(0), 0xff, 0xd9]), {
    headers: {
      'Content-Type': 'image/jpeg',
      'X-Spot-Image-At': String((Date.now() - 30000) / 1000),
      'X-Spot-Image-Age-Ms': '30000',
      'X-Spot-Image-Source': suppressed ? 'cache' : 'camera',
      'X-Spot-Image-Upstream-Suppressed': suppressed ? '1' : '0',
      ...(suppressed ? { 'X-Spot-Image-Suppression-Reason': 'storage_pressure', 'Retry-After': retry } : {}),
    },
  }
);

describe('useSpotViewModelEffects image lifecycle', () => {
  afterEach(() => {
    delete window.smartFactoryElectron;
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

  it('rechecks suppressed JPEGs before delayed onLoad without resetting recovery or duplicating timers', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    let serial = 0;
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => `blob:pressure-${++serial}`);
      static revokeObjectURL = vi.fn();
    });
    service.config.mockResolvedValue({ ...SPOT_CONFIG, image_refresh_interval: 0.25 });
    service.image.mockResolvedValueOnce(new Response('', { status: 502 }))
      .mockImplementation(async () => imageResponse(true));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      await act(async () => { await vi.advanceTimersByTimeAsync(500); });
      const firstUrl = result.current.imageUrl;
      expect(firstUrl).toBe('blob:pressure-1');
      expect(result.current.metadata?.source).toBe('cache');
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(service.image).toHaveBeenCalledTimes(3);
      const currentUrl = result.current.imageUrl;
      act(() => { result.current.handleImageLoad(firstUrl); result.current.handleImageLoad(currentUrl); });
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(250); });
      expect(service.image).toHaveBeenCalledTimes(3);
      await act(async () => { await vi.advanceTimersByTimeAsync(1750); });
      expect(service.image).toHaveBeenCalledTimes(4);
      service.image.mockImplementation(async () => imageResponse(false));
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      act(() => { result.current.handleImageLoad(result.current.imageUrl); });
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(0);
      await act(async () => { await vi.advanceTimersByTimeAsync(250); });
      expect(service.image).toHaveBeenCalledTimes(6);
    } finally { unmount(); vi.unstubAllGlobals(); }
  });

  it('releases replaced pending URLs and restores the last displayed image after a pressure display failure', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    const alive = new Set<string>();
    let serial = 0;
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => { const url = `blob:owned-${++serial}`; alive.add(url); return url; });
      static revokeObjectURL = vi.fn((url: string) => { alive.delete(url); });
    });
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementationOnce(async () => imageResponse(false))
      .mockImplementation(async () => imageResponse(true));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      const displayedUrl = result.current.imageUrl;
      act(() => { result.current.handleImageLoad(displayedUrl); result.current.refreshImage(); });
      await act(async () => undefined);
      for (let replacement = 0; replacement < 4; replacement += 1) {
        const pendingUrl = result.current.imageUrl;
        await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
        expect(alive.has(pendingUrl)).toBe(false);
        expect(alive).toEqual(new Set([displayedUrl, result.current.imageUrl]));
        const currentUrl = result.current.imageUrl;
        act(() => { result.current.handleImageLoad(pendingUrl); result.current.handleImageError(pendingUrl); });
        expect(result.current.diagnostics.error_count).toBe(0);
        expect(result.current.imageUrl).toBe(currentUrl);
        expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
      }
      act(() => { result.current.handleImageError(result.current.imageUrl); });
      expect(result.current.imageUrl).toBe(displayedUrl);
      expect(alive).toEqual(new Set([displayedUrl]));
      expect(result.current.diagnostics.error_count).toBe(1);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(true);
    } finally { unmount(); vi.unstubAllGlobals(); }
    expect(alive.size).toBe(0);
  });

  it('clears pressure timers on hide and resumes once through the real visibility effect', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    const schedule = vi.spyOn(window, 'setTimeout');
    const cancel = vi.spyOn(window, 'clearTimeout');
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementation(async () => new Response('', { status: 503, headers: {
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '2',
    } }));
    const { unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      expect(service.image).toHaveBeenCalledTimes(1);
      const pressureTimerIndex = schedule.mock.calls.findIndex((call) => call[1] === 2000);
      expect(pressureTimerIndex).toBeGreaterThanOrEqual(0);
      const pressureTimer = schedule.mock.results[pressureTimerIndex].value;
      act(() => { setVisibilityState('hidden'); document.dispatchEvent(new Event('visibilitychange')); });
      expect(cancel).toHaveBeenCalledWith(pressureTimer);
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { setVisibilityState('visible'); document.dispatchEvent(new Event('visibilitychange')); });
      expect(service.image).toHaveBeenCalledTimes(2);
      await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
      expect(service.image).toHaveBeenCalledTimes(2);
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(service.image).toHaveBeenCalledTimes(3);
    } finally { unmount(); }
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(service.image).toHaveBeenCalledTimes(3);
  });

  it('discards a response owned by the old configuration and fetches the new source after draining it', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => 'blob:new-source');
      static revokeObjectURL = vi.fn();
    });
    let finishOld!: (response: Response) => void;
    let finishNew!: (response: Response) => void;
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { finishNew = resolve; }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      service.config.mockResolvedValue({ ...SPOT_CONFIG, image_url: '/api/spot/new-image.jpg' });
      await act(async () => { await result.current.refreshConfig(); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { finishOld(imageResponse(true)); });
      expect(URL.createObjectURL).not.toHaveBeenCalled();
      expect(service.image).toHaveBeenCalledTimes(2);
      expect(service.image).toHaveBeenLastCalledWith('/api/spot/new-image.jpg');
      await act(async () => { finishNew(imageResponse(false)); });
      expect(result.current.imageUrl).toBe('blob:new-source');
      expect(result.current.diagnostics.error_count).toBe(0);
      expect(result.current.lastSuccessAt).toBe(Date.now() - 30000);
    } finally { unmount(); vi.unstubAllGlobals(); }
  });

  it('preserves the displayed capture metadata when a later pressure response has no image', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => 'blob:preserved');
      static revokeObjectURL = vi.fn();
    });
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementationOnce(async () => imageResponse(true))
      .mockImplementation(async () => new Response('', { status: 503, headers: {
        'X-Spot-Image-Upstream-Suppressed': '1',
        'X-Spot-Image-Suppression-Reason': 'storage_pressure',
        'Retry-After': '2',
      } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      const capturedAt = Date.now() - 30000;
      act(() => { result.current.handleImageLoad(result.current.imageUrl); });
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(result.current.metadata?.captured_at).toBe(capturedAt);
      expect(result.current.metadata?.source).toBe('cache');
      expect(result.current.lastSuccessAt).toBe(capturedAt);
      expect(result.current.imageUrl).toBe('blob:preserved');
      expect(result.current.metadata?.image_upstream_suppressed).toBe(true);
      expect(result.current.diagnostics.error_count).toBe(0);
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(service.image).toHaveBeenCalledTimes(3);
    } finally { unmount(); vi.unstubAllGlobals(); }
  });

  it('replaces a fallback pressure timer when the configured refresh interval changes', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementation(async () => new Response('', { status: 503, headers: {
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '0',
    } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      await act(async () => { await vi.advanceTimersByTimeAsync(500); });
      expect(service.image).toHaveBeenCalledTimes(1);
      service.config.mockResolvedValue({ ...SPOT_CONFIG, image_refresh_interval: 0.25 });
      await act(async () => { await result.current.refreshConfig(); });
      await act(async () => { await vi.advanceTimersByTimeAsync(999); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(service.image).toHaveBeenCalledTimes(2);
      await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
      expect(service.image).toHaveBeenCalledTimes(3); // no leftover request at the original 3s deadline
      expect(result.current.diagnostics.error_count).toBe(0);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(0);
    } finally { unmount(); }
  });

  it('does not turn a large positive Retry-After into an immediate retry through timer overflow', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementation(async () => new Response('', { status: 503, headers: {
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '2147484',
    } }));
    const { unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(service.image).toHaveBeenCalledTimes(1);
    } finally { unmount(); }
  });

  it('records a late transport failure while hidden without scheduling or spending an automatic retry', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    let reject!: (error: Error) => void;
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementationOnce(() => new Promise((_resolve, rejectResponse) => { reject = rejectResponse; }))
      .mockImplementation(async () => new Response('', { status: 503, headers: {
        'X-Spot-Image-Upstream-Suppressed': '1',
        'X-Spot-Image-Suppression-Reason': 'storage_pressure',
        'Retry-After': '2',
      } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      act(() => { setVisibilityState('hidden'); document.dispatchEvent(new Event('visibilitychange')); });
      await act(async () => { reject(new Error('actual network failure')); });
      expect(result.current.diagnostics.error_count).toBe(1);
      expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(0);
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { setVisibilityState('visible'); document.dispatchEvent(new Event('visibilitychange')); });
      expect(service.image).toHaveBeenCalledTimes(2);
      expect(result.current.diagnostics.error_count).toBe(1);
    } finally { unmount(); }
  });

  it('keeps the pressure deadline when only presentation configuration changes', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementation(async () => new Response('', { status: 503, headers: {
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '2',
    } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      await act(async () => { await vi.advanceTimersByTimeAsync(500); });
      service.config.mockResolvedValue({ ...SPOT_CONFIG, widget_width: 640 });
      await act(async () => { await result.current.refreshConfig(); });
      await act(async () => { await vi.advanceTimersByTimeAsync(1499); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(service.image).toHaveBeenCalledTimes(2);
    } finally { unmount(); }
  });

  it('drains a suppressed response body after unmount without allocating a URL or starting another timer', async () => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => 'blob:must-not-be-created');
      static revokeObjectURL = vi.fn();
    });
    const listeners = new Set<(stopping: boolean) => void | Promise<void>>();
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: vi.fn(async () => ({ ok: true })),
      isShuttingDown: () => false,
      onShutdownStateChanged: (listener) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    };
    let finishBody!: () => void;
    const body = new ReadableStream<Uint8Array>({ start(controller) {
      finishBody = () => {
        controller.enqueue(new Uint8Array([0xff, 0xd8, ...Array<number>(16).fill(0), 0xff, 0xd9]));
        controller.close();
      };
    } });
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockResolvedValueOnce(new Response(body, { headers: {
      'Content-Type': 'image/jpeg',
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      'Retry-After': '1',
    } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      expect(result.current.diagnostics.in_flight).toBe(true);
      unmount();
      let drained = false;
      const draining = Promise.all(Array.from(listeners, (listener) => listener(true))).then(() => { drained = true; });
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(drained).toBe(false);
      await act(async () => { finishBody(); await draining; });
      expect(drained).toBe(true);
      expect(listeners.size).toBe(0);
      expect(URL.createObjectURL).not.toHaveBeenCalled();
      await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
      expect(service.image).toHaveBeenCalledTimes(1);
    } finally { unmount(); vi.unstubAllGlobals(); }
  });

  it.each(['unflagged-503', 'invalid-pressure-jpeg'])('keeps %s in the ordinary error path', async (kind) => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementation(async () => kind === 'unflagged-503'
      ? new Response('', { status: 503, headers: { 'Retry-After': '2' } })
      : new Response('<html>broken</html>', { headers: {
        'Content-Type': 'image/jpeg',
        'X-Spot-Image-Upstream-Suppressed': '1',
        'X-Spot-Image-Suppression-Reason': 'storage_pressure',
        'Retry-After': '2',
      } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      expect(result.current.diagnostics.error_count).toBe(1);
      expect(result.current.imageUrl).toBe('');
      if (kind === 'unflagged-503') {
        expect(result.current.diagnostics.consecutive_retry_attempt).toBe(1);
        await act(async () => { await vi.advanceTimersByTimeAsync(500); });
        expect(service.image).toHaveBeenCalledTimes(2);
      } else {
        expect(result.current.diagnostics.automatic_retry_pending).toBe(false);
        await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
        expect(service.image).toHaveBeenCalledTimes(1);
      }
    } finally { unmount(); }
  });

  it.each([null, '-1', '1.5', 'invalid'])('uses the configured positive fallback for Retry-After %s', async (retry) => {
    vi.useFakeTimers();
    setVisibilityState('visible');
    service.config.mockResolvedValue(SPOT_CONFIG);
    service.image.mockImplementation(async () => new Response('', { status: 503, headers: {
      'X-Spot-Image-Upstream-Suppressed': '1',
      'X-Spot-Image-Suppression-Reason': 'storage_pressure',
      ...(retry === null ? {} : { 'Retry-After': retry }),
    } }));
    const { result, unmount } = renderHook(() => useSpotViewModel());
    try {
      await act(async () => undefined);
      await act(async () => { await vi.advanceTimersByTimeAsync(2999); });
      expect(service.image).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(service.image).toHaveBeenCalledTimes(2);
      expect(result.current.diagnostics.error_count).toBe(0);
      expect(result.current.diagnostics.consecutive_retry_attempt).toBe(0);
    } finally { unmount(); }
  });

  it('cancels pending retry and normal refresh while hidden, then resumes once when visible', async () => {
    setVisibilityState('visible');
    const fetchInitialImage = vi.fn(async () => undefined);
    const loadConfig = vi.fn(async () => null);
    const applySpotConfig = vi.fn();
    const cancelPendingImageRetry = vi.fn();
    const cancelNormalImageRefresh = vi.fn();
    const cancelStoragePressureRecheck = vi.fn();
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
        cancelStoragePressureRecheck,
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
