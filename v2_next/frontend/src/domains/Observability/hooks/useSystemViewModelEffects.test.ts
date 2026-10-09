import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HealthSnapshot } from '../../../shared/types';
import {
  POLL_REQUEST_TIMEOUT_MS,
  STARTUP_HEALTH_REQUEST_TIMEOUT_MS,
} from '../../../shared/api/pollingRequest';
import { useSystemViewModelEffects } from './useSystemViewModelEffects';
import { SUPERSEDED_HEALTH_REQUEST } from './useSystemViewModel.health';

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
        intervalMs: 2_000,
        failureCount: 0,
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
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

  it('accepts the leader health cadence on a follower without issuing its own request', async () => {
    const now = Date.now();
    window.localStorage.setItem('dashboard_polling_leader_v1', JSON.stringify({ tab_id: 'other-tab', updated_at: now }));
    const fetchHealth = vi.fn().mockResolvedValue(null);
    const fetchStats = vi.fn().mockResolvedValue(null);
    const applyHealthSnapshot = vi.fn();
    const setHealthPolling = vi.fn();
    const health = { running: true } as HealthSnapshot;
    const { unmount } = renderHook(() => useSystemViewModelEffects({
      fetchHealth, fetchStats, reconnectBusy: false, setHealthPolling,
      setStatsPolling: vi.fn(), applyHealthSnapshot, applyStatsSnapshot: vi.fn(),
      setDashboardLeaderState: vi.fn(), setPollingPausedByVisibility: vi.fn(),
    }));
    try {
      await act(async () => {
        window.dispatchEvent(new StorageEvent('storage', {
          key: 'dashboard_system_broadcast_v1',
          newValue: JSON.stringify({ tab_id: 'other-tab', kind: 'health', data: health, sent_at: now }),
        }));
        await vi.advanceTimersByTimeAsync(2500);
      });
      expect(fetchHealth).not.toHaveBeenCalled();
      expect(fetchStats).not.toHaveBeenCalled();
      expect(applyHealthSnapshot).toHaveBeenCalledWith(health, now);
      expect(setHealthPolling).toHaveBeenLastCalledWith({ degraded: false, intervalMs: 2000, failureCount: 0 });
    } finally {
      unmount();
      expect(vi.getTimerCount()).toBe(0);
    }
  });

  it('keeps the sender identity and increasing sequence across clock corrections and effect restarts', async () => {
    const health = {running: true} as HealthSnapshot;
    const fetchHealth = vi.fn().mockResolvedValue(health);
    const params = {
      fetchHealth, fetchStats: vi.fn().mockResolvedValue(null), setHealthPolling: vi.fn(),
      setStatsPolling: vi.fn(), applyHealthSnapshot: vi.fn(), applyStatsSnapshot: vi.fn(),
      setDashboardLeaderState: vi.fn(), setPollingPausedByVisibility: vi.fn(),
    };
    const {unmount, rerender} = renderHook(({busy}) => useSystemViewModelEffects({...params, reconnectBusy: busy}),
      {initialProps: {busy: false}});
    const last = () => JSON.parse(window.localStorage.getItem('dashboard_system_broadcast_v1') ?? '{}');
    try {
      await act(async () => {await vi.advanceTimersByTimeAsync(0);});
      const first = last();
      expect(first.kind).toBe('health');
      expect(first.source_id).toEqual(expect.any(String));
      expect(first.source_id.length).toBeGreaterThan(0);
      expect(first.health_sequence).toBe(1);
      vi.setSystemTime(Date.now() - 60000);
      await act(async () => {await vi.advanceTimersByTimeAsync(2000);});
      expect(last().source_id).toBe(first.source_id);
      expect(last().health_sequence).toBe(2);
      expect(last().sent_at).toBeLessThan(first.sent_at);
      rerender({busy: true});
      rerender({busy: false});
      await act(async () => {await vi.advanceTimersByTimeAsync(0);});
      expect(last().source_id).toBe(first.source_id);
      expect(last().health_sequence).toBe(3);
      // jsdom queues storage events when the leader lock and payload are written.
      await act(async () => {await vi.advanceTimersByTimeAsync(50);});
    } finally {
      unmount();
      // Releasing the lock queues a final jsdom storage event after cleanup.
      const callsAfterUnmount = fetchHealth.mock.calls.length;
      await act(async () => {await vi.advanceTimersByTimeAsync(50);});
      expect(vi.getTimerCount()).toBe(0);
      expect(fetchHealth).toHaveBeenCalledTimes(callsAfterUnmount);
    }
  });

  it('keeps the prior failure cadence and broadcast when a request is superseded', async () => {
    const health = { running: true } as HealthSnapshot;
    const fetchHealth = vi.fn<(timeoutMs?: number) => Promise<HealthSnapshot | null | typeof SUPERSEDED_HEALTH_REQUEST>>()
      .mockResolvedValueOnce(health)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(SUPERSEDED_HEALTH_REQUEST)
      .mockResolvedValue(health);
    const setHealthPolling = vi.fn();
    const { unmount } = renderHook(() => useSystemViewModelEffects({
      fetchHealth, fetchStats: vi.fn().mockResolvedValue(null), reconnectBusy: false,
      setHealthPolling, setStatsPolling: vi.fn(), applyHealthSnapshot: vi.fn(),
      applyStatsSnapshot: vi.fn(), setDashboardLeaderState: vi.fn(), setPollingPausedByVisibility: vi.fn(),
    }));
    try {
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(setHealthPolling).toHaveBeenLastCalledWith({ degraded: true, intervalMs: 5000, failureCount: 1 });
      const broadcast = window.localStorage.getItem('dashboard_system_broadcast_v1');
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(fetchHealth).toHaveBeenCalledTimes(3);
      expect(setHealthPolling).toHaveBeenLastCalledWith({ degraded: true, intervalMs: 5000, failureCount: 1 });
      expect(window.localStorage.getItem('dashboard_system_broadcast_v1')).toBe(broadcast);
      await act(async () => { await vi.advanceTimersByTimeAsync(4999); });
      expect(fetchHealth).toHaveBeenCalledTimes(3);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(fetchHealth).toHaveBeenCalledTimes(4);
      expect(fetchHealth).toHaveBeenLastCalledWith(POLL_REQUEST_TIMEOUT_MS);
      expect(setHealthPolling).toHaveBeenLastCalledWith({ degraded: false, intervalMs: 2000, failureCount: 0 });
    } finally {
      unmount();
      await act(async () => { await vi.advanceTimersByTimeAsync(50); });
      expect(vi.getTimerCount()).toBe(0);
    }
  });

  it('keeps the full failure delay if publishing a successful response fails', async () => {
    const setItem = Storage.prototype.setItem;
    const storageSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, key, value) {
      if (key === 'dashboard_system_broadcast_v1') throw new Error('Synthetic storage failure');
      return setItem.call(this, key, value);
    });
    const health = { running: true } as HealthSnapshot;
    const fetchHealth = vi.fn(() => new Promise<HealthSnapshot>(resolve => {
      window.setTimeout(() => resolve(health), 500);
    }));
    const setHealthPolling = vi.fn();
    const { unmount } = renderHook(() => useSystemViewModelEffects({
      fetchHealth, fetchStats: vi.fn().mockResolvedValue(null), reconnectBusy: false,
      setHealthPolling, setStatsPolling: vi.fn(), applyHealthSnapshot: vi.fn(),
      applyStatsSnapshot: vi.fn(), setDashboardLeaderState: vi.fn(), setPollingPausedByVisibility: vi.fn(),
    }));
    try {
      await act(async () => { await vi.advanceTimersByTimeAsync(500); });
      expect(setHealthPolling).toHaveBeenLastCalledWith({ degraded: true, intervalMs: 5000, failureCount: 1 });
      await act(async () => { await vi.advanceTimersByTimeAsync(4999); });
      expect(fetchHealth).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(fetchHealth).toHaveBeenCalledTimes(2);
    } finally {
      unmount();
      await act(async () => { await vi.advanceTimersByTimeAsync(500); });
      storageSpy.mockRestore();
      expect(vi.getTimerCount()).toBe(0);
    }
  });
});
