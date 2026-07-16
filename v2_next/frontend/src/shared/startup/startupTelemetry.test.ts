import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  armDashboardOperationalReadyTimeout,
  isOperationalFactoryData,
  isStartupFactoryDataSnapshot,
  markBackendHealthReady,
  markFirstDataSnapshotReady,
  markFirstLiveDataReady,
  OPERATIONAL_READY_TIMEOUT_MS,
  recordDashboardReadyAfterPaint,
  recordStartupEvent,
  recordStartupEventOnce,
} from './startupTelemetry';
import type { FactoryData, HealthSnapshot } from '../types';

type StartupTelemetryWindow = Window & {
  __SF_STARTUP_EVENT_KEYS__?: Set<string>;
  __SF_STARTUP_EVENT_PENDING_KEYS__?: Set<string>;
  __SF_OPERATIONAL_READY_STATE__?: unknown;
};

const resetStartupTelemetryState = (): void => {
  const startupWindow = window as StartupTelemetryWindow;
  delete startupWindow.__SF_STARTUP_EVENT_KEYS__;
  delete startupWindow.__SF_STARTUP_EVENT_PENDING_KEYS__;
  delete startupWindow.__SF_OPERATIONAL_READY_STATE__;
};

const buildHealth = (overrides: Partial<HealthSnapshot> = {}): HealthSnapshot => ({
  running: true,
  thread_alive: true,
  last_update: null,
  driver_connected: true,
  mode: 'real',
  runtime_kind: 'packaged',
  ...overrides,
});

const buildFactoryData = (overrides: Partial<FactoryData> = {}): FactoryData => ({
  Time: '2026-07-15 12:00:00',
  Status: 'Running',
  timestamp_ms: 1_752_570_000_000,
  ...overrides,
} as FactoryData);

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

    expect(recordStartup).toHaveBeenCalledWith(
      'renderer.index-render',
      expect.objectContaining({
        protocol: 'file:',
        renderer_time_origin_ms: expect.any(Number),
        renderer_now_ms: expect.any(Number),
        renderer_epoch_ms: expect.any(Number),
      })
    );
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
    expect(recordStartup).toHaveBeenCalledWith(
      'renderer.app-import-start',
      expect.objectContaining({
        route: '/first',
        renderer_time_origin_ms: expect.any(Number),
        renderer_now_ms: expect.any(Number),
        renderer_epoch_ms: expect.any(Number),
      })
    );
  });

  it('retries a rejected one-shot event and commits the key only after acceptance', async () => {
    vi.useFakeTimers();
    const recordStartup = vi.fn()
      .mockResolvedValueOnce({ ok: false, reason: 'temporarily_rejected' })
      .mockResolvedValueOnce({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };

    recordStartupEventOnce('retry-key', 'renderer.app-import-start');
    await vi.advanceTimersByTimeAsync(250);
    recordStartupEventOnce('retry-key', 'renderer.app-import-start');

    expect(recordStartup).toHaveBeenCalledTimes(2);
  });

  it('records an informational timeout fallback and still accepts a later RAF paint', () => {
    vi.useFakeTimers();
    const frameCallbacks: FrameRequestCallback[] = [];
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback): number => {
      frameCallbacks.push(callback);
      return frameCallbacks.length;
    }));
    vi.stubGlobal('cancelAnimationFrame', vi.fn());

    const cleanup = recordDashboardReadyAfterPaint('native', { widget_count: 3 });

    vi.advanceTimersByTime(4999);
    expect(recordStartup).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);

    expect(recordStartup).toHaveBeenCalledTimes(1);
    expect(recordStartup).toHaveBeenCalledWith(
      'renderer.dashboard-paint-fallback',
      expect.objectContaining({
        surface: 'native',
        ready_strategy: 'timeout-fallback',
        widget_count: 3,
      })
    );

    frameCallbacks[0](16);
    frameCallbacks[1](32);
    expect(recordStartup).toHaveBeenCalledTimes(2);
    expect(recordStartup).toHaveBeenLastCalledWith(
      'renderer.dashboard-ready',
      expect.objectContaining({ ready_strategy: 'raf' })
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

  it.each([
    ['missing timestamp', { timestamp_ms: null }],
    ['zero timestamp', { timestamp_ms: 0 }],
    ['NaN timestamp', { timestamp_ms: Number.NaN }],
    ['infinite timestamp', { timestamp_ms: Number.POSITIVE_INFINITY }],
    ['blank time', { Time: '  ' }],
    ['blank status', { Status: '  ' }],
    ['initializing status', { Status: 'Initializing' }],
    ['offline status', { Status: 'Offline' }],
    ['error status', { Status: 'Error' }],
  ])('rejects %s as operational factory data', (_name, overrides) => {
    expect(isOperationalFactoryData(buildFactoryData(overrides))).toBe(false);
  });

  it('accepts a timestamped offline snapshot for startup handoff without claiming live data', () => {
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };
    const offlineData = buildFactoryData({ Status: 'Offline' });

    expect(isStartupFactoryDataSnapshot(offlineData)).toBe(true);
    expect(isStartupFactoryDataSnapshot(buildFactoryData({ Status: 'Initializing' }))).toBe(false);
    expect(isStartupFactoryDataSnapshot(buildFactoryData({ Status: 'Unexpected' }))).toBe(false);
    expect(markFirstDataSnapshotReady(offlineData)).toBe(true);
    expect(markFirstDataSnapshotReady(offlineData)).toBe(false);
    expect(markFirstLiveDataReady(offlineData)).toBe(false);
    expect(recordStartup).toHaveBeenCalledTimes(1);
    expect(recordStartup).toHaveBeenCalledWith(
      'renderer.first-data-snapshot',
      expect.objectContaining({ status: 'Offline', timestamp_present: true })
    );
  });

  it('accepts timestamped non-initial factory data and records each response gate once', () => {
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };

    expect(markBackendHealthReady(null)).toBe(false);
    expect(markBackendHealthReady(buildHealth({ running: false }))).toBe(false);
    expect(markBackendHealthReady(buildHealth())).toBe(true);
    expect(markBackendHealthReady(buildHealth())).toBe(false);
    expect(markFirstLiveDataReady(buildFactoryData({ timestamp_ms: 0 }))).toBe(false);
    expect(markFirstLiveDataReady(buildFactoryData())).toBe(true);
    expect(markFirstLiveDataReady(buildFactoryData())).toBe(false);

    expect(recordStartup).toHaveBeenCalledTimes(2);
    expect(recordStartup).toHaveBeenNthCalledWith(
      1,
      'renderer.backend-health-ready',
      expect.objectContaining({ running: true, driver_connected: true })
    );
    expect(recordStartup).toHaveBeenNthCalledWith(
      2,
      'renderer.first-live-data',
      expect.objectContaining({ status: 'Running', timestamp_present: true })
    );
  });

  it.each([
    ['backend-data-paint', ['backend', 'data', 'paint']],
    ['paint-data-backend', ['paint', 'data', 'backend']],
  ])('records operational ready after all gates and two final frames: %s', (_name, order) => {
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

    const runGate = (gate: string): void => {
      if (gate === 'backend') {
        markBackendHealthReady(buildHealth());
      } else if (gate === 'data') {
        markFirstLiveDataReady(buildFactoryData());
      } else {
        recordDashboardReadyAfterPaint('native');
        const firstDashboardFrame = frameCallbacks.shift();
        firstDashboardFrame?.(0);
        const secondDashboardFrame = frameCallbacks.shift();
        secondDashboardFrame?.(16);
      }
    };

    order.forEach(runGate);

    expect(
      recordStartup.mock.calls.some(([eventName]) => eventName === 'renderer.dashboard-operational-ready')
    ).toBe(false);
    const firstOperationalFrame = frameCallbacks.shift();
    firstOperationalFrame?.(32);
    expect(
      recordStartup.mock.calls.some(([eventName]) => eventName === 'renderer.dashboard-operational-ready')
    ).toBe(false);
    const secondOperationalFrame = frameCallbacks.shift();
    secondOperationalFrame?.(48);

    const operationalCalls = recordStartup.mock.calls.filter(
      ([eventName]) => eventName === 'renderer.dashboard-operational-ready'
    );
    expect(operationalCalls).toHaveLength(1);
    expect(operationalCalls[0][1]).toEqual(expect.objectContaining({
      ready_strategy: 'raf',
      required_gates: 'backend_health,live_data,dashboard_paint',
      surface: 'native',
    }));

    markBackendHealthReady(buildHealth());
    markFirstLiveDataReady(buildFactoryData());
    expect(recordStartup.mock.calls.filter(
      ([eventName]) => eventName === 'renderer.dashboard-operational-ready'
    )).toHaveLength(1);
  });

  it('records missing gates at the operational timeout without fabricating readiness', () => {
    vi.useFakeTimers();
    const recordStartup = vi.fn().mockResolvedValue({ ok: true });
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: recordStartup,
    };

    armDashboardOperationalReadyTimeout();
    armDashboardOperationalReadyTimeout();
    markBackendHealthReady(buildHealth());
    vi.advanceTimersByTime(OPERATIONAL_READY_TIMEOUT_MS);

    const timeoutCalls = recordStartup.mock.calls.filter(
      ([eventName]) => eventName === 'renderer.dashboard-operational-timeout'
    );
    const readyCalls = recordStartup.mock.calls.filter(
      ([eventName]) => eventName === 'renderer.dashboard-operational-ready'
    );
    expect(timeoutCalls).toHaveLength(1);
    expect(timeoutCalls[0][1]).toEqual(expect.objectContaining({
      missing_gates: 'live_data,dashboard_paint',
      timeout_ms: OPERATIONAL_READY_TIMEOUT_MS,
    }));
    expect(readyCalls).toHaveLength(0);
  });
});
