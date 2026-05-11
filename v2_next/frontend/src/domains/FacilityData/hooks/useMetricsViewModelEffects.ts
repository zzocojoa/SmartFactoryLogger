import { useEffect } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { DashboardLeaderState, FactoryData } from '../../../shared/types';
import { buildSeriesSample } from '../timeseries/seriesSampling';
import type { SeriesBuffer } from '../timeseries/seriesBuffer';
import type { WorkerDataPayload, WorkerOutboundMessage } from '../workers/polling.worker.types';
import {
  createPollingWorker,
  fetchLatestMetricOnMainThreadWithLatency,
  releasePollingWorker,
  startPollingWorker,
  stopPollingWorker,
} from './useMetricsViewModel.service';
import {
  clearDashboardLeaderLock,
  readDashboardLeaderLock,
  readOrCreateDashboardTabId,
  writeDashboardLeaderLock,
} from '../../../shared/utils/dashboardPollingLeader';

interface UseMetricsPollingEffectsParams {
  pollIntervalMs: number;
  seriesBufferRef: MutableRefObject<SeriesBuffer>;
  setData: Dispatch<SetStateAction<FactoryData | null>>;
  setConnected: Dispatch<SetStateAction<boolean>>;
  setLastDataAt: Dispatch<SetStateAction<number | null>>;
  setLatencyMs: Dispatch<SetStateAction<number | null>>;
  setPollingDegraded: Dispatch<SetStateAction<boolean>>;
  setPollingIntervalMs: Dispatch<SetStateAction<number>>;
  setPollingFailureCount: Dispatch<SetStateAction<number>>;
  setDashboardLeaderState: Dispatch<SetStateAction<DashboardLeaderState | null>>;
  setPollingPausedByVisibility: Dispatch<SetStateAction<boolean>>;
}

const BACKOFF_MULTIPLIERS = [1, 2, 4, 10];
const DASHBOARD_TAB_ID_KEY = 'dashboard_polling_tab_id_v1';
const DASHBOARD_LEADER_KEY = 'dashboard_polling_leader_v1';
const LEADER_HEARTBEAT_MS = 4000;
const LEADER_TAKEOVER_MS = 30000;

interface DashboardDataBroadcast {
  tab_id: string;
  payload: WorkerDataPayload;
  sent_at: number;
}

const handleWorkerDataMessage = (
  payload: WorkerDataPayload,
  params: Omit<UseMetricsPollingEffectsParams, 'pollIntervalMs' | 'seriesBufferRef'> & {
    seriesBufferRef: MutableRefObject<SeriesBuffer>;
  }
) => {
  const { data, timestamp, latency } = payload;
  params.setData(data);
  params.setConnected(true);
  params.setLastDataAt(timestamp);
  params.setLatencyMs(Math.round(latency));
  params.setPollingDegraded(payload.failure_count > 0);
  params.setPollingIntervalMs(payload.poll_interval_ms);
  params.setPollingFailureCount(payload.failure_count);
  params.seriesBufferRef.current.append(buildSeriesSample(data, timestamp));
};

const resolveIntervalMs = (requestedIntervalMs: number, failureCount: number): number => {
  if (failureCount <= 0) {
    return requestedIntervalMs;
  }
  const multiplierIndex = Math.min(failureCount, BACKOFF_MULTIPLIERS.length) - 1;
  return requestedIntervalMs * BACKOFF_MULTIPLIERS[multiplierIndex];
};

export const useMetricsPollingEffects = ({
  pollIntervalMs,
  seriesBufferRef,
  setData,
  setConnected,
  setLastDataAt,
  setLatencyMs,
  setPollingDegraded,
  setPollingIntervalMs,
  setPollingFailureCount,
  setDashboardLeaderState,
  setPollingPausedByVisibility,
}: UseMetricsPollingEffectsParams) => {
  useEffect(() => {
    let worker: Worker | null = null;
    let channel: BroadcastChannel | null = null;
    let disposed = false;
    let usingMainThreadFallback = false;
    let mainThreadTimerId: number | null = null;
    let heartbeatTimerId: number | null = null;
    let mainThreadFailureCount = 0;
    let pollingPaused = typeof document !== 'undefined' && document.visibilityState === 'hidden';
    const tabId = readOrCreateDashboardTabId(DASHBOARD_TAB_ID_KEY);
    let leaderState: DashboardLeaderState = {
      tab_id: tabId,
      mode: typeof window === 'undefined' ? 'standalone' : 'recovering',
      leader_tab_id: null,
      last_broadcast_at: null,
    };

    const updateLeaderState = (nextState: DashboardLeaderState): void => {
      leaderState = nextState;
      setDashboardLeaderState(nextState);
    };

    const isLeader = (): boolean => leaderState.mode === 'leader' || leaderState.mode === 'standalone';

    const clearMainThreadTimer = (): void => {
      if (mainThreadTimerId !== null) {
        window.clearTimeout(mainThreadTimerId);
        mainThreadTimerId = null;
      }
    };

    const clearHeartbeatTimer = (): void => {
      if (heartbeatTimerId !== null) {
        window.clearInterval(heartbeatTimerId);
        heartbeatTimerId = null;
      }
    };

    const applyDataPayload = (payload: WorkerDataPayload): void => {
      handleWorkerDataMessage(payload, {
        seriesBufferRef,
        setData,
        setConnected,
        setLastDataAt,
        setLatencyMs,
        setPollingDegraded,
        setPollingIntervalMs,
        setPollingFailureCount,
        setDashboardLeaderState,
        setPollingPausedByVisibility,
      });
    };

    const broadcastPayload = (payload: WorkerDataPayload): void => {
      if (typeof window === 'undefined') {
        return;
      }
      const message: DashboardDataBroadcast = {
        tab_id: tabId,
        payload,
        sent_at: Date.now(),
      };
      channel?.postMessage(message);
      updateLeaderState({
        tab_id: tabId,
        mode: leaderState.mode === 'standalone' ? 'standalone' : 'leader',
        leader_tab_id: tabId,
        last_broadcast_at: message.sent_at,
      });
    };

    const scheduleMainThreadPoll = (delayMs: number): void => {
      if (disposed || !usingMainThreadFallback || pollingPaused || !isLeader()) {
        return;
      }
      clearMainThreadTimer();
      mainThreadTimerId = window.setTimeout(() => {
        void runMainThreadPoll();
      }, delayMs);
    };

    const runMainThreadPoll = async (): Promise<void> => {
      if (disposed || !usingMainThreadFallback || pollingPaused || !isLeader()) {
        return;
      }

      try {
        const payload = await fetchLatestMetricOnMainThreadWithLatency();
        mainThreadFailureCount = 0;
        const nextPayload = {
          ...payload,
          poll_interval_ms: pollIntervalMs,
          failure_count: mainThreadFailureCount,
        };
        applyDataPayload(nextPayload);
        broadcastPayload(nextPayload);
      } catch (error) {
        mainThreadFailureCount += 1;
        const nextIntervalMs = resolveIntervalMs(pollIntervalMs, mainThreadFailureCount);
        console.error('API Error (MainThread)', error);
        setConnected(false);
        setLatencyMs(null);
        setPollingDegraded(true);
        setPollingIntervalMs(nextIntervalMs);
        setPollingFailureCount(mainThreadFailureCount);
        scheduleMainThreadPoll(nextIntervalMs);
        return;
      }

      scheduleMainThreadPoll(pollIntervalMs);
    };

    const startMainThreadFallback = (reason: string): void => {
      if (disposed || usingMainThreadFallback || !isLeader()) {
        return;
      }
      usingMainThreadFallback = true;
      console.warn(`[PollingFallback] Switching to main thread polling: ${reason}`);
      if (worker) {
        try {
          stopPollingWorker(worker);
        } catch (error) {
          console.error('Worker stop failed during fallback', error);
        }
        releasePollingWorker(worker);
        worker = null;
      }
      if (!pollingPaused) {
        scheduleMainThreadPoll(0);
      }
    };

    const stopPolling = (): void => {
      clearMainThreadTimer();
      if (worker) {
        try {
          stopPollingWorker(worker);
        } catch (error) {
          console.error('Worker stop failed', error);
        }
      }
    };

    const startPolling = (): void => {
      if (disposed || pollingPaused || !isLeader()) {
        return;
      }
      if (usingMainThreadFallback) {
        scheduleMainThreadPoll(0);
        return;
      }
      if (!worker) {
        try {
          worker = createPollingWorker();
        } catch (error) {
          console.error('Worker creation failed', error);
          startMainThreadFallback('worker creation failed');
          return;
        }
        worker.onmessage = (event: MessageEvent<WorkerOutboundMessage>) => {
          const { type, payload } = event.data;
          if (type === 'DATA') {
            applyDataPayload(payload);
            broadcastPayload(payload);
            return;
          }

          console.error('API Error (Worker)', payload.message);
          setConnected(false);
          setLatencyMs(null);
          setPollingDegraded(payload.failure_count > 0);
          setPollingIntervalMs(payload.poll_interval_ms);
          setPollingFailureCount(payload.failure_count);
        };

        worker.onerror = (event: ErrorEvent) => {
          console.error('Worker runtime error', event.message);
          startMainThreadFallback(event.message || 'worker runtime error');
        };

        worker.onmessageerror = () => {
          console.error('Worker message error');
          startMainThreadFallback('worker message error');
        };
      }
      if (worker) {
        startPollingWorker(worker, pollIntervalMs);
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
        startPolling();
        return;
      }

      pollingPaused = document.visibilityState === 'hidden';
      setPollingPausedByVisibility(pollingPaused);
      if (pollingPaused) {
        stopPolling();
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
        startPolling();
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
        startPolling();
        return;
      }

      stopPolling();
      updateLeaderState({
        tab_id: tabId,
        mode: lockAge >= LEADER_TAKEOVER_MS ? 'recovering' : 'follower',
        leader_tab_id: currentLock.tab_id,
        last_broadcast_at: leaderState.last_broadcast_at,
      });
    };

    if (typeof BroadcastChannel === 'function') {
      channel = new BroadcastChannel('smartfactory-dashboard-data');
      channel.onmessage = (event: MessageEvent<DashboardDataBroadcast>) => {
        const payload = event.data;
        if (!payload || payload.tab_id === tabId || isLeader()) {
          return;
        }
        applyDataPayload(payload.payload);
        updateLeaderState({
          tab_id: tabId,
          mode: leaderState.mode === 'recovering' ? 'recovering' : 'follower',
          leader_tab_id: payload.tab_id,
          last_broadcast_at: payload.sent_at,
        });
      };
    }

    const handleVisibility = (): void => {
      reconcileLeadership();
    };

    const handleStorage = (event: StorageEvent): void => {
      if (event.key === DASHBOARD_LEADER_KEY) {
        reconcileLeadership();
      }
    };

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibility);
    }
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

    reconcileLeadership();

    return () => {
      disposed = true;
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibility);
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('storage', handleStorage);
      }
      clearHeartbeatTimer();
      clearMainThreadTimer();
      if (worker) {
        stopPollingWorker(worker);
        releasePollingWorker(worker);
      }
      if (channel) {
        channel.close();
      }
      clearDashboardLeaderLock(DASHBOARD_LEADER_KEY, tabId);
    };
  }, [
    pollIntervalMs,
    seriesBufferRef,
    setConnected,
    setData,
    setLastDataAt,
    setLatencyMs,
    setPollingDegraded,
    setPollingIntervalMs,
    setPollingFailureCount,
    setDashboardLeaderState,
    setPollingPausedByVisibility,
  ]);
};
