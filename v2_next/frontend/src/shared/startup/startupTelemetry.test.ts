import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  recordDashboardReadyAfterPaint,
  recordStartupEvent,
  recordStartupEventOnce,
} from './startupTelemetry';

type StartupTelemetryWindow = Window & {
  __SF_STARTUP_EVENT_KEYS__?: Set<string>;
};

const resetStartupTelemetryState = (): void => {
  const startupWindow = window as StartupTelemetryWindow;
  delete startupWindow.__SF_STARTUP_EVENT_KEYS__;
};

afterEach(() => {
  delete window.smartFactoryElectron;
  resetStartupTelemetryState();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('startupTelemetry', () => {
  it('returns a browser fallback when the Electron bridge is unavailable', async () => {
    delete window.smartFactoryElectron;

    const result = await recordStartupEvent('renderer.index-boot', { route: '/dashboard' });

    expect(result).toEqual({ ok: false, skipped: 'bridge_unavailable' });
  });

  it('invokes the constrained Electron startup bridge when available', async () => {
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };

    const result = await recordStartupEvent('renderer.index-render', { protocol: 'file:' });

    expect(recordStartup).toHaveBeenCalledWith('renderer.index-render', { protocol: 'file:' });
    expect(result).toEqual({ ok: true });
  });

  it('deduplicates explicit startup events by key', () => {
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };

    recordStartupEventOnce('same-key', 'renderer.app-import-start', { route: '/first' });
    recordStartupEventOnce('same-key', 'renderer.app-import-start', { route: '/second' });

    expect(recordStartup).toHaveBeenCalledTimes(1);
    expect(recordStartup).toHaveBeenCalledWith('renderer.app-import-start', { route: '/first' });
  });

  it('records dashboard ready with a timeout fallback when animation frames are throttled', () => {
    vi.useFakeTimers();
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };
    vi.stubGlobal('requestAnimationFrame', vi.fn((): number => 1));
    vi.stubGlobal('cancelAnimationFrame', vi.fn());

    const cleanup = recordDashboardReadyAfterPaint('native', { widget_count: 3 });

    vi.advanceTimersByTime(4999);
    expect(recordStartup).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);

    expect(recordStartup).toHaveBeenCalledTimes(1);
    expect(recordStartup).toHaveBeenCalledWith(
      'renderer.dashboard-ready',
      expect.objectContaining({
        surface: 'native',
        ready_strategy: 'timeout-fallback',
        widget_count: 3,
      })
    );

    cleanup();
  });

  it('records dashboard ready after two animation frames and only once', () => {
    const frameCallbacks: FrameRequestCallback[] = [];
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback): number => {
      frameCallbacks.push(callback);
      return frameCallbacks.length;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());

    const cleanup = recordDashboardReadyAfterPaint('native', { widget_count: 7 });

    expect(recordStartup).not.toHaveBeenCalled();
    frameCallbacks[0](0);
    expect(recordStartup).not.toHaveBeenCalled();
    frameCallbacks[1](16);

    expect(recordStartup).toHaveBeenCalledTimes(1);
    expect(recordStartup).toHaveBeenCalledWith(
      'renderer.dashboard-ready',
      expect.objectContaining({
        surface: 'native',
        route: '/',
        ready_state: document.readyState,
        ready_strategy: 'raf',
        widget_count: 7,
      })
    );

    recordDashboardReadyAfterPaint('scene', { layout_editing: true });
    frameCallbacks[2](32);
    frameCallbacks[3](48);

    expect(recordStartup).toHaveBeenCalledTimes(1);
    cleanup();
  });
});
