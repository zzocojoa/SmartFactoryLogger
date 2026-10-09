import { useEffect, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { CommLogInfo, DashboardLeaderState, HealthSnapshot, StatsSnapshot } from '../../../shared/types';
import {
  POLL_REQUEST_TIMEOUT_MS,
  STARTUP_HEALTH_REQUEST_TIMEOUT_MS,
} from '../../../shared/api/pollingRequest';
import { SUPERSEDED_HEALTH_REQUEST } from './useSystemViewModel.health';
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
  fetchHealth: (timeoutMs?: number, mayApply?: () => boolean) => Promise<HealthSnapshot | null | typeof SUPERSEDED_HEALTH_REQUEST>;
  fetchStats: () => Promise<StatsSnapshot | null>;
  reconnectBusy: boolean;
  setHealthPolling: Dispatch<SetStateAction<PollingState>>;
  setStatsPolling: Dispatch<SetStateAction<PollingState>>;
  applyHealthSnapshot: (snapshot: HealthSnapshot, sentAtMs?: number) => boolean | void;
  applyStatsSnapshot: Dispatch<SetStateAction<StatsSnapshot | null>>;
  setDashboardLeaderState: Dispatch<SetStateAction<DashboardLeaderState | null>>;
  setPollingPausedByVisibility: Dispatch<SetStateAction<boolean>>;
}

const BASE_POLL_INTERVAL_MS = 5000;
// Refresh the UI's health snapshot before the SPOT badge's 5s stale boundary.
// This is API polling only; device sampling, timeouts and failure backoff stay unchanged.
const HEALTH_POLL_INTERVAL_MS = 2000;
const BACKOFF_MULTIPLIERS = [1, 2, 4, 10];
const DASHBOARD_TAB_ID_KEY = 'dashboard_polling_tab_id_v1';
const DASHBOARD_LEADER_KEY = 'dashboard_polling_leader_v1';
const DASHBOARD_SYSTEM_BROADCAST_KEY = 'dashboard_system_broadcast_v1';
const COMM_LOG_BROADCAST_KEY = 'settings_comm_log_broadcast_v1';
const LEADER_HEARTBEAT_MS = 4000;
const LEADER_TAKEOVER_MS = 30000;
const LEGACY_HEALTH_HISTORY_LIMIT = 256;
const HEALTH_SOURCE_HISTORY_LIMIT = 256;

interface DashboardSystemBroadcast {
  tab_id: string;
  kind: 'health' | 'stats';
  data: HealthSnapshot | StatsSnapshot;
  sent_at: number;
  source_id?: string;
  health_sequence?: number;
}

interface CommLogInfoBroadcast {
  tab_id: string;
  kind: 'comm-metrics';
  data: CommLogInfo;
  sent_at: number;
}

const readStoredCommLogSnapshot = (): CommLogInfoBroadcast | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(COMM_LOG_BROADCAST_KEY);
    if (!raw) {
      return null;
    }
    const payload = JSON.parse(raw) as CommLogInfoBroadcast;
    return payload.kind === 'comm-metrics' ? payload : null;
  } catch {
    return null;
  }
};

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
  const healthBroadcastRef = useRef<{ sourceId: string | null; sequence: number }>({ sourceId: null, sequence: 0 });
  const receivedHealthSequencesRef = useRef(new Map<string, number>());
  const receivedLegacyHealthRef = useRef(new Set<string>());
  useEffect(() => {
    let mounted = true;
    let healthTimeoutId: number | null = null;
    let statsTimeoutId: number | null = null;
    let heartbeatTimerId: number | null = null;
    let channel: BroadcastChannel | null = null;
    let healthFailures = 0;
    let healthHasSucceeded = false;
    let healthInFlight = false;
    let sourceConfirmation: { candidates: Map<string, number>; arriving: Map<string, number> } | null = null;
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
    const isPackagedStartupRecoveryPending = (): boolean =>
      typeof window !== 'undefined' &&
      Boolean(window.smartFactoryElectron?.recordStartupEvent) &&
      !healthHasSucceeded;
    const canPollHealth = (): boolean => isLeader() || isPackagedStartupRecoveryPending();
    const isHealthVisibilityBlocked = (): boolean =>
      document.visibilityState === 'hidden' && !isPackagedStartupRecoveryPending();

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
      if (kind === 'health') {
        const broadcast = healthBroadcastRef.current;
        broadcast.sourceId ??= typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
          ? crypto.randomUUID() : `health-${Math.random().toString(36).slice(2)}`;
        payload.source_id = broadcast.sourceId;
        payload.health_sequence = ++broadcast.sequence;
      }
      try {
        channel?.postMessage(payload);
      } catch {
        // Async poll results can arrive after StrictMode cleanup closes the channel.
      }
      window.localStorage.setItem(DASHBOARD_SYSTEM_BROADCAST_KEY, JSON.stringify(payload));
      updateLeaderState({
        tab_id: tabId,
        mode: leaderState.mode === 'standalone' ? 'standalone' : 'leader',
        leader_tab_id: tabId,
        last_broadcast_at: payload.sent_at,
      });
    };

    const pollHealth = async () => {
      if (!mounted || !canPollHealth() || healthInFlight) return;
      healthInFlight = true;
      const cycleStartedAt = performance.now();
      let succeeded = false;
      try {
        if (!reconnectBusy) {
          const healthTimeoutMs = healthHasSucceeded
            ? POLL_REQUEST_TIMEOUT_MS
            : STARTUP_HEALTH_REQUEST_TIMEOUT_MS;
          const data = await fetchHealth(healthTimeoutMs);
          if (!mounted || !canPollHealth() || isHealthVisibilityBlocked()) return;
          if (data === SUPERSEDED_HEALTH_REQUEST) {
            // A newer direct request owns this observation. Do not publish the
            // old result or count supersession as a communication failure.
          } else if (data) {
            healthHasSucceeded = true;
            healthFailures = 0;
            healthDelayMs = HEALTH_POLL_INTERVAL_MS;
            broadcastSystem('health', data);
            succeeded = true;
          } else {
            healthFailures += 1;
            healthDelayMs = healthHasSucceeded
              ? resolveBackoffDelay(BASE_POLL_INTERVAL_MS, healthFailures)
              : BASE_POLL_INTERVAL_MS;
          }
        } else {
          healthFailures = 0;
          healthDelayMs = BASE_POLL_INTERVAL_MS;
        }
      } catch (e) {
        console.error('Health poll failed', e);
        healthFailures += 1;
        healthDelayMs = healthHasSucceeded
          ? resolveBackoffDelay(BASE_POLL_INTERVAL_MS, healthFailures)
          : BASE_POLL_INTERVAL_MS;
      } finally {
        healthInFlight = false;
      }
      if (!mounted) return;
      setHealthPolling(buildPollingState(healthDelayMs, healthFailures));
      if (mounted && canPollHealth() && !isHealthVisibilityBlocked()) {
        const elapsedMs = performance.now() - cycleStartedAt;
        // Successful polls use start-to-start cadence. A startup overrun skips
        // missed ticks; it never creates a catch-up burst or overlaps a request.
        const nextDelayMs = succeeded && elapsedMs >= 0 && elapsedMs < healthDelayMs
          ? healthDelayMs - elapsedMs
          : healthDelayMs;
        healthTimeoutId = window.setTimeout(pollHealth, nextDelayMs);
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
      if (!mounted) {
        return;
      }
      if (canPollHealth() && !isHealthVisibilityBlocked()) {
        healthTimeoutId = window.setTimeout(pollHealth, reconnectBusy ? BASE_POLL_INTERVAL_MS : 0);
      }
      if (isLeader() && document.visibilityState !== 'hidden') {
        statsTimeoutId = window.setTimeout(pollStats, reconnectBusy ? BASE_POLL_INTERVAL_MS + 500 : 500);
      }
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
      const startupRecoveryPending = isPackagedStartupRecoveryPending();
      setPollingPausedByVisibility(hidden && !startupRecoveryPending);
      if (hidden && !startupRecoveryPending) {
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
      if (startupRecoveryPending && currentLock?.tab_id !== tabId) {
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

    const rememberHealthSource = (history: Map<string, number>, source: string, sequence: number): void => {
      if (!history.has(source) && history.size >= HEALTH_SOURCE_HISTORY_LIMIT) {
        history.delete(history.keys().next().value!);
      }
      history.set(source, Math.max(sequence, history.get(source) ?? 0));
    };

    const canConfirmSource = (): boolean => mounted && !reconnectBusy
      && document.visibilityState !== 'hidden' && !isLeader();

    const confirmHealthSources = (sources: ReadonlyMap<string, number>): void => {
      if (!canConfirmSource()) return;
      const candidates = new Map<string, number>();
      sources.forEach((sequence, source) => {
        if (sequence > (receivedHealthSequencesRef.current.get(source) ?? 0)) rememberHealthSource(candidates, source, sequence);
      });
      if (!candidates.size) return;
      if (sourceConfirmation) {
        const pending = sourceConfirmation;
        candidates.forEach((sequence, source) => {
          if (sequence > (pending.candidates.get(source) ?? 0)) rememberHealthSource(pending.arriving, source, sequence);
        });
        return;
      }
      const confirmation = { candidates, arriving: new Map<string, number>() };
      sourceConfirmation = confirmation;
      const mayApply = () => canConfirmSource() && sourceConfirmation === confirmation;
      // The evicted sender's payload cannot prove it is newer than the screen.
      // Only the current API response owns the receipt; never replay that payload.
      void fetchHealth(POLL_REQUEST_TIMEOUT_MS, mayApply).then(data => {
        if (!mayApply() || !data || data === SUPERSEDED_HEALTH_REQUEST) return;
        confirmation.candidates.forEach((sequence, source) =>
          rememberHealthSource(receivedHealthSequencesRef.current, source, sequence));
      }).catch(error => {
        if (mayApply()) console.error('Health source confirmation failed', error);
      }).finally(() => {
        if (sourceConfirmation !== confirmation) return;
        sourceConfirmation = null;
        // Arrivals after the request began need their own authoritative check.
        // Failed candidates stay unregistered and retry on the next message.
        if (confirmation.arriving.size) confirmHealthSources(confirmation.arriving);
      });
    };

    const applyBroadcast = (payload: DashboardSystemBroadcast): void => {
      if (payload.kind === 'health') {
        if (payload.source_id !== undefined || payload.health_sequence !== undefined) {
          if (typeof payload.source_id !== 'string' || !payload.source_id
            || !Number.isSafeInteger(payload.health_sequence) || (payload.health_sequence ?? 0) <= 0) return;
          const source = JSON.stringify([payload.tab_id, payload.source_id]);
          const sequence = payload.health_sequence as number;
          const history = receivedHealthSequencesRef.current;
          if (sequence <= (history.get(source) ?? 0)) return;
          if (sourceConfirmation?.candidates.has(source) || sourceConfirmation?.arriving.has(source)
            || (!history.has(source) && history.size >= HEALTH_SOURCE_HISTORY_LIMIT)) {
            confirmHealthSources(new Map([[source, sequence]]));
            return;
          }
          rememberHealthSource(history, source, sequence);
        } else {
          // The second transport can deliver A after B. Remember more than just
          // the last payload without using wall-clock timestamps for ordering.
          const fingerprint = JSON.stringify(payload);
          const history = receivedLegacyHealthRef.current;
          if (history.has(fingerprint)) return;
          history.add(fingerprint);
          if (history.size > LEGACY_HEALTH_HISTORY_LIMIT) history.delete(history.values().next().value!);
        }
        const accepted = applyHealthSnapshot(payload.data as HealthSnapshot,
          typeof payload.sent_at === 'number' && Number.isFinite(payload.sent_at) ? payload.sent_at : NaN);
        if (accepted === false) return;
        healthHasSucceeded = true;
        healthFailures = 0;
        healthDelayMs = HEALTH_POLL_INTERVAL_MS;
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

interface UseCommLogInfoEffectsParams {
  enabled: boolean;
  settingsLeaderMode: DashboardLeaderState['mode'] | null;
  settingsPollingPausedByVisibility: boolean;
  pollingPausedByVisibility: boolean;
  loadCommLogInfo: () => Promise<CommLogInfo | null>;
  applyCommLogInfoSnapshot: (next: CommLogInfo) => void;
}

export const useCommLogInfoEffects = ({
  enabled,
  settingsLeaderMode,
  settingsPollingPausedByVisibility,
  pollingPausedByVisibility,
  loadCommLogInfo,
  applyCommLogInfoSnapshot,
}: UseCommLogInfoEffectsParams) => {
  const syncKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    let mounted = true;
    let channel: BroadcastChannel | null = null;
    const tabId = readOrCreateDashboardTabId(DASHBOARD_TAB_ID_KEY);

    const applyBroadcast = (payload: CommLogInfoBroadcast): void => {
      if (!mounted || payload.tab_id === tabId) {
        return;
      }
      applyCommLogInfoSnapshot(payload.data);
    };

    const publishSnapshot = (data: CommLogInfo): void => {
      const payload: CommLogInfoBroadcast = {
        tab_id: tabId,
        kind: 'comm-metrics',
        data,
        sent_at: Date.now(),
      };
      try {
        channel?.postMessage(payload);
      } catch {
        // Async loads can resolve after StrictMode cleanup closes the channel.
      }
      window.localStorage.setItem(COMM_LOG_BROADCAST_KEY, JSON.stringify(payload));
    };

    const leaderAllowed = settingsLeaderMode === 'leader' || settingsLeaderMode === 'standalone';
    const hidden = document.visibilityState === 'hidden';
    const shouldSync =
      enabled &&
      leaderAllowed &&
      !settingsPollingPausedByVisibility &&
      !pollingPausedByVisibility &&
      !hidden;

    if (typeof BroadcastChannel === 'function') {
      channel = new BroadcastChannel('smartfactory-settings-comm-log');
      channel.onmessage = (event: MessageEvent<CommLogInfoBroadcast>) => {
        const payload = event.data;
        if (!payload || payload.kind !== 'comm-metrics') {
          return;
        }
        applyBroadcast(payload);
      };
    }

    const handleStorage = (event: StorageEvent): void => {
      if (event.key !== COMM_LOG_BROADCAST_KEY || !event.newValue) {
        return;
      }
      try {
        const payload = JSON.parse(event.newValue) as CommLogInfoBroadcast;
        if (payload.kind !== 'comm-metrics') {
          return;
        }
        applyBroadcast(payload);
      } catch {
        return;
      }
    };

    window.addEventListener('storage', handleStorage);

    if (!enabled) {
      syncKeyRef.current = null;
    } else if (!leaderAllowed) {
      const stored = readStoredCommLogSnapshot();
      if (stored) {
        applyBroadcast(stored);
      }
    } else if (shouldSync) {
      const nextSyncKey = `${tabId}:${settingsLeaderMode ?? 'standalone'}`;
      if (syncKeyRef.current !== nextSyncKey) {
        syncKeyRef.current = nextSyncKey;
        void loadCommLogInfo().then((data) => {
          if (!mounted || !data) {
            return;
          }
          applyCommLogInfoSnapshot(data);
          publishSnapshot(data);
        });
      }
    }

    return () => {
      mounted = false;
      window.removeEventListener('storage', handleStorage);
      channel?.close();
    };
  }, [
    applyCommLogInfoSnapshot,
    enabled,
    loadCommLogInfo,
    pollingPausedByVisibility,
    settingsLeaderMode,
    settingsPollingPausedByVisibility,
  ]);
};
