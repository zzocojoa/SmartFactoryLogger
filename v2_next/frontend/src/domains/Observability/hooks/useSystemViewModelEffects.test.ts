import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HealthSnapshot } from '../../../shared/types';
import {
  POLL_REQUEST_TIMEOUT_MS,
  STARTUP_HEALTH_REQUEST_TIMEOUT_MS,
} from '../../../shared/api/pollingRequest';
import { useSystemViewModelEffects } from './useSystemViewModelEffects';

const setVisibilityState = (visibilityState: DocumentVisibilityState): void => {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => visibilityState,
  });
};

describe('useSystemViewModelEffects startup recovery', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
    window.sessionStorage.clear();
    setVisibilityState('visible');
    delete window.smartFactoryElectron;
    vi.stubGlobal('BroadcastChannel', undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete window.smartFactoryElectron;
  });

  it('keeps the base health interval until the first successful response', async () => {
    const health = { running: true } as HealthSnapshot;
    const fetchHealth = vi
      .fn<(timeoutMs?: number) => Promise<HealthSnapshot | null>>()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null)
      .mockResolvedValue(health);
    const fetchStats = vi.fn().mockResolvedValue(null);
    const setHealthPolling = vi.fn();

    const { unmount } = renderHook(() =>
      useSystemViewModelEffects({
        fetchHealth,
        fetchStats,
        reconnectBusy: false,
        setHealthPolling,
        setStatsPolling: vi.fn(),
        applyHealthSnapshot: vi.fn(),
        applyStatsSnapshot: vi.fn(),
        setDashboardLeaderState: vi.fn(),
        setPollingPausedByVisibility: vi.fn(),
      })
    );

    try {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(1);
      expect(fetchHealth).toHaveBeenLastCalledWith(STARTUP_HEALTH_REQUEST_TIMEOUT_MS);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(2);
      expect(fetchHealth).toHaveBeenLastCalledWith(STARTUP_HEALTH_REQUEST_TIMEOUT_MS);
      expect(setHealthPolling).toHaveBeenLastCalledWith({
        degraded: true,
        intervalMs: 5_000,
        failureCount: 2,
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(3);
      expect(fetchHealth).toHaveBeenLastCalledWith(STARTUP_HEALTH_REQUEST_TIMEOUT_MS);
      expect(setHealthPolling).toHaveBeenLastCalledWith({
        degraded: false,
        intervalMs: 5_000,
        failureCount: 0,
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(4);
      expect(fetchHealth).toHaveBeenLastCalledWith(POLL_REQUEST_TIMEOUT_MS);
    } finally {
      unmount();
    }
  });

  it('recovers packaged startup health while hidden and a stale leader lock exists', async () => {
    setVisibilityState('hidden');
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: vi.fn(),
    };
    window.localStorage.setItem(
      'dashboard_polling_leader_v1',
      JSON.stringify({ tab_id: 'stale-tab', updated_at: Date.now() })
    );
    const health = { running: true } as HealthSnapshot;
    const fetchHealth = vi
      .fn<(timeoutMs?: number) => Promise<HealthSnapshot | null>>()
      .mockResolvedValueOnce(null)
      .mockResolvedValue(health);
    const fetchStats = vi.fn().mockResolvedValue(null);

    const { unmount } = renderHook(() =>
      useSystemViewModelEffects({
        fetchHealth,
        fetchStats,
        reconnectBusy: false,
        setHealthPolling: vi.fn(),
        setStatsPolling: vi.fn(),
        applyHealthSnapshot: vi.fn(),
        applyStatsSnapshot: vi.fn(),
        setDashboardLeaderState: vi.fn(),
        setPollingPausedByVisibility: vi.fn(),
      })
    );

    try {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(1);
      expect(fetchStats).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(2);
    } finally {
      unmount();
    }
  });
});
