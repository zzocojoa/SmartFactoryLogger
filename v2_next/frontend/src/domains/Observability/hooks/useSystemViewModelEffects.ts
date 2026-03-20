import { useEffect } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { DashboardLeaderState, HealthSnapshot, StatsSnapshot } from '../../../shared/types';
import {
  clearDashboardLeaderLock,
  readDashboardLeaderLock,
  readOrCreateDashboardTabId,
  writeDashboardLeaderLock,
} from '../../../shared/utils/dashboardPollingLeader';

interface PollingState {
  degraded: boolean;
  intervalMs: number;
  failureCount: number;
}

interface UseSystemViewModelEffectsParams {
  fetchHealth: () => Promise<HealthSnapshot | null>;
  fetchStats: () => Promise<StatsSnapshot | null>;
  reconnectBusy: boolean;
  setHealthPolling: Dispatch<SetStateAction<PollingState>>;
  setStatsPolling: Dispatch<SetStateAction<PollingState>>;
  applyHealthSnapshot: Dispatch<SetStateAction<HealthSnapshot | null>>;
  applyStatsSnapshot: Dispatch<SetStateAction<StatsSnapshot | null>>;
  setDashboardLeaderState: Dispatch<SetStateAction<DashboardLeaderState | null>>;
  setPollingPausedByVisibility: Dispatch<SetStateAction<boolean>>;
}

const BASE_POLL_INTERVAL_MS = 5000;
const BACKOFF_MULTIPLIERS = [1, 2, 4, 10];
const DASHBOARD_TAB_ID_KEY = 'dashboard_polling_tab_id_v1';
const DASHBOARD_LEADER_KEY = 'dashboard_polling_leader_v1';
const DASHBOARD_SYSTEM_BROADCAST_KEY = 'dashboard_system_broadcast_v1';
const LEADER_HEARTBEAT_MS = 4000;
const LEADER_TAKEOVER_MS = 30000;

interface DashboardSystemBroadcast {
  tab_id: string;
  kind: 'health' | 'stats';
  data: HealthSnapshot | StatsSnapshot;
  sent_at: number;
}

const buildPollingState = (intervalMs: number, failureCount: number): PollingState => ({
  degraded: failureCount > 0,
  intervalMs,
  failureCount,
});

const resolveBackoffDelay = (baseIntervalMs: number, failureCount: number) => {
  if (failureCount <= 0) {
    return baseIntervalMs;
  }
  const multiplierIndex = Math.min(failureCount, BACKOFF_MULTIPLIERS.length) - 1;
  return baseIntervalMs * BACKOFF_MULTIPLIERS[multiplierIndex];
};

export const useSystemViewModelEffects = ({
  fetchHealth,
  fetchStats,
  reconnectBusy,
  setHealthPolling,
  setStatsPolling,
  applyHealthSnapshot,
  applyStatsSnapshot,
  setDashboardLeaderState,
  setPollingPausedByVisibility,
}: UseSystemViewModelEffectsParams) => {
  useEffect(() => {
    let mounted = true;
    let healthTimeoutId: number | null = null;
    let statsTimeoutId: number | null = null;
    let heartbeatTimerId: number | null = null;
    let channel: BroadcastChannel | null = null;
    let healthFailures = 0;
    let statsFailures = 0;
    let healthDelayMs = BASE_POLL_INTERVAL_MS;
    let statsDelayMs = BASE_POLL_INTERVAL_MS;
    const tabId = readOrCreateDashboardTabId(DASHBOARD_TAB_ID_KEY);
    let leaderState: DashboardLeaderState = {
      tab_id: tabId,
      mode: typeof window === 'undefined' ? 'standalone' : 'recovering',
      leader_tab_id: null,
      last_broadcast_at: null,
    };

    setHealthPolling(buildPollingState(healthDelayMs, healthFailures));
    setStatsPolling(buildPollingState(statsDelayMs, statsFailures));

    const updateLeaderState = (nextState: DashboardLeaderState): void => {
      leaderState = nextState;
      setDashboardLeaderState(nextState);
    };

    const isLeader = (): boolean => leaderState.mode === 'leader' || leaderState.mode === 'standalone';

    const clearTimers = (): void => {
      if (healthTimeoutId !== null) {
        window.clearTimeout(healthTimeoutId);
        healthTimeoutId = null;
      }
      if (statsTimeoutId !== null) {
        window.clearTimeout(statsTimeoutId);
        statsTimeoutId = null;
      }
    };

    const broadcastSystem = (
      kind: 'health' | 'stats',
      data: HealthSnapshot | StatsSnapshot
    ): void => {
      if (typeof window === 'undefined') {
        return;
      }
      const payload: DashboardSystemBroadcast = {
        tab_id: tabId,
        kind,
        data,
        sent_at: Date.now(),
      };
      channel?.postMessage(payload);
      window.localStorage.setItem(DASHBOARD_SYSTEM_BROADCAST_KEY, JSON.stringify(payload));
      updateLeaderState({
        tab_id: tabId,
        mode: leaderState.mode === 'standalone' ? 'standalone' : 'leader',
        leader_tab_id: tabId,
        last_broadcast_at: payload.sent_at,
      });
    };

    const pollHealth = async () => {
      if (!mounted || !isLeader()) return;
      if (!reconnectBusy) {
        try {
          const data = await fetchHealth();
          if (data) {
            healthFailures = 0;
            healthDelayMs = BASE_POLL_INTERVAL_MS;
            broadcastSystem('health', data);
          } else {
            healthFailures += 1;
            healthDelayMs = resolveBackoffDelay(BASE_POLL_INTERVAL_MS, healthFailures);
          }
        } catch (e) {
          console.error('Health poll failed', e);
          healthFailures += 1;
          healthDelayMs = resolveBackoffDelay(BASE_POLL_INTERVAL_MS, healthFailures);
        }
      } else {
        healthFailures = 0;
        healthDelayMs = BASE_POLL_INTERVAL_MS;
      }
      setHealthPolling(buildPollingState(healthDelayMs, healthFailures));
      if (mounted && isLeader() && document.visibilityState !== 'hidden') {
        healthTimeoutId = window.setTimeout(pollHealth, healthDelayMs);
      }
    };

    const pollStats = async () => {
      if (!mounted || !isLeader()) return;
      if (!reconnectBusy) {
        try {
          const data = await fetchStats();
          if (data) {
            statsFailures = 0;
            statsDelayMs = BASE_POLL_INTERVAL_MS;
            broadcastSystem('stats', data);
          } else {
            statsFailures += 1;
            statsDelayMs = resolveBackoffDelay(BASE_POLL_INTERVAL_MS, statsFailures);
          }
        } catch (e) {
          console.error('Stats poll failed', e);
          statsFailures += 1;
          statsDelayMs = resolveBackoffDelay(BASE_POLL_INTERVAL_MS, statsFailures);
        }
      } else {
        statsFailures = 0;
        statsDelayMs = BASE_POLL_INTERVAL_MS;
      }
      setStatsPolling(buildPollingState(statsDelayMs, statsFailures));
      if (mounted && isLeader() && document.visibilityState !== 'hidden') {
        statsTimeoutId = window.setTimeout(pollStats, statsDelayMs);
      }
    };

    const schedulePolling = (): void => {
      clearTimers();
      if (!mounted || !isLeader() || document.visibilityState === 'hidden') {
        return;
      }
      healthTimeoutId = window.setTimeout(pollHealth, reconnectBusy ? BASE_POLL_INTERVAL_MS : 0);
      statsTimeoutId = window.setTimeout(pollStats, reconnectBusy ? BASE_POLL_INTERVAL_MS + 500 : 500);
    };

    const reconcileLeadership = (): void => {
      if (typeof window === 'undefined' || typeof document === 'undefined') {
        updateLeaderState({
          tab_id: tabId,
          mode: 'standalone',
          leader_tab_id: null,
          last_broadcast_at: leaderState.last_broadcast_at,
        });
        schedulePolling();
        return;
      }

      const hidden = document.visibilityState === 'hidden';
      setPollingPausedByVisibility(hidden);
      if (hidden) {
        clearTimers();
        clearDashboardLeaderLock(DASHBOARD_LEADER_KEY, tabId);
        updateLeaderState({
          tab_id: tabId,
          mode: 'follower',
          leader_tab_id: null,
          last_broadcast_at: leaderState.last_broadcast_at,
        });
        return;
      }

      const now = Date.now();
      const currentLock = readDashboardLeaderLock(DASHBOARD_LEADER_KEY);
      if (!currentLock || currentLock.tab_id === tabId) {
        writeDashboardLeaderLock(DASHBOARD_LEADER_KEY, { tab_id: tabId, updated_at: now });
        updateLeaderState({
          tab_id: tabId,
          mode: 'leader',
          leader_tab_id: tabId,
          last_broadcast_at: leaderState.last_broadcast_at,
        });
        schedulePolling();
        return;
      }

      const lockAge = now - currentLock.updated_at;
      if (lockAge >= LEADER_TAKEOVER_MS) {
        writeDashboardLeaderLock(DASHBOARD_LEADER_KEY, { tab_id: tabId, updated_at: now });
        updateLeaderState({
          tab_id: tabId,
          mode: 'leader',
          leader_tab_id: tabId,
          last_broadcast_at: leaderState.last_broadcast_at,
        });
        schedulePolling();
        return;
      }

      clearTimers();
      updateLeaderState({
        tab_id: tabId,
        mode: lockAge >= LEADER_TAKEOVER_MS ? 'recovering' : 'follower',
        leader_tab_id: currentLock.tab_id,
        last_broadcast_at: leaderState.last_broadcast_at,
      });
    };

    const applyBroadcast = (payload: DashboardSystemBroadcast): void => {
      if (payload.kind === 'health') {
        applyHealthSnapshot(payload.data as HealthSnapshot);
        healthFailures = 0;
        healthDelayMs = BASE_POLL_INTERVAL_MS;
        setHealthPolling(buildPollingState(healthDelayMs, healthFailures));
      } else {
        applyStatsSnapshot(payload.data as StatsSnapshot);
        statsFailures = 0;
        statsDelayMs = BASE_POLL_INTERVAL_MS;
        setStatsPolling(buildPollingState(statsDelayMs, statsFailures));
      }
      updateLeaderState({
        tab_id: tabId,
        mode: 'follower',
        leader_tab_id: payload.tab_id,
        last_broadcast_at: payload.sent_at,
      });
    };

    if (typeof BroadcastChannel === 'function') {
      channel = new BroadcastChannel('smartfactory-dashboard-system');
      channel.onmessage = (event: MessageEvent<DashboardSystemBroadcast>) => {
        const payload = event.data;
        if (!payload || payload.tab_id === tabId || isLeader()) {
          return;
        }
        applyBroadcast(payload);
      };
    }

    const handleStorage = (event: StorageEvent): void => {
      if (event.key === DASHBOARD_LEADER_KEY) {
        reconcileLeadership();
        return;
      }
      if (event.key !== DASHBOARD_SYSTEM_BROADCAST_KEY || isLeader()) {
        return;
      }
      if (!event.newValue) {
        return;
      }
      try {
        const payload = JSON.parse(event.newValue) as DashboardSystemBroadcast;
        if (payload.tab_id === tabId) {
          return;
        }
        applyBroadcast(payload);
      } catch {
        return;
      }
    };

    const handleVisibility = (): void => {
      reconcileLeadership();
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('storage', handleStorage);
      heartbeatTimerId = window.setInterval(() => {
        if (isLeader()) {
          writeDashboardLeaderLock(DASHBOARD_LEADER_KEY, { tab_id: tabId, updated_at: Date.now() });
          return;
        }
        reconcileLeadership();
      }, LEADER_HEARTBEAT_MS);
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibility);
    }

    reconcileLeadership();

    return () => {
      mounted = false;
      clearTimers();
      if (heartbeatTimerId !== null) {
        window.clearInterval(heartbeatTimerId);
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('storage', handleStorage);
      }
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibility);
      }
      if (channel) {
        channel.close();
      }
      clearDashboardLeaderLock(DASHBOARD_LEADER_KEY, tabId);
    };
  }, [
    applyHealthSnapshot,
    applyStatsSnapshot,
    fetchHealth,
    fetchStats,
    reconnectBusy,
    setDashboardLeaderState,
    setHealthPolling,
    setPollingPausedByVisibility,
    setStatsPolling,
  ]);
};
