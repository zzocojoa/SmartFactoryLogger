import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HealthSnapshot } from '../../../shared/types';
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
    vi.stubGlobal('BroadcastChannel', undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('keeps the base health interval until the first successful response', async () => {
    const health = { running: true } as HealthSnapshot;
    const fetchHealth = vi
      .fn<() => Promise<HealthSnapshot | null>>()
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

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(2);
      expect(setHealthPolling).toHaveBeenLastCalledWith({
        degraded: true,
        intervalMs: 5_000,
        failureCount: 2,
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(fetchHealth).toHaveBeenCalledTimes(3);
      expect(setHealthPolling).toHaveBeenLastCalledWith({
        degraded: false,
        intervalMs: 5_000,
        failureCount: 0,
      });
    } finally {
      unmount();
    }
  });
});
