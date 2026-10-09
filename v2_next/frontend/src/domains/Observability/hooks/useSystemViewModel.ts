import { useState, useCallback, useRef, useEffect } from 'react';
import { systemService } from '../api/systemService';
import type {
  CommLogInfo,
  ConnectionTestState,
  DashboardLeaderState,
  FrontendErrorEntry,
  HealthSnapshot,
  ObservabilityErrorsResponse,
  PathHealthResult,
  PathHealthState,
  StatsSnapshot,
} from '../../../shared/types';
import { buildPathHealthFallback } from './useSystemViewModel.selectors';
import { assessSpotObservation, buildHealthReceipt, includeHealthDeliveryAge, mergeHealthSnapshot,
  SUPERSEDED_HEALTH_REQUEST } from './useSystemViewModel.health';
import type { HealthState, SpotObservation } from './useSystemViewModel.health';
import {
  persistCommLogPath,
  persistExportPath,
  readPersistedCommLogPath,
  readPersistedExportPath,
} from './useSystemViewModel.service';
import { useSystemViewModelEffects } from './useSystemViewModelEffects';
import type { PollingState, UseSystemViewModel } from './useSystemViewModel.types';

const DEFAULT_POLLING_STATE: PollingState = {
  degraded: false,
  intervalMs: 5000,
  failureCount: 0,
};
const SPOT_IDENTITY_HISTORY_LIMIT = 256;

export const useSystemViewModel = (): UseSystemViewModel => {
  const [{ health, healthReceipt }, setHealthState] = useState<HealthState>({ health: null, healthReceipt: null });
  const spotObservationRef = useRef<SpotObservation | null>(null);
  const retiredSpotServicesRef = useRef(new Set<string>());
  const healthRequestSequenceRef = useRef(0);
  const mountedRef = useRef(true);
  const confirmSpotServiceRef = useRef<((serviceIds: ReadonlySet<string>) => void) | null>(null);
  const pendingSpotServicesRef = useRef<{ candidates: Set<string>; arriving: Set<string> } | null>(null);
  const rejectedSpotServicesRef = useRef(new Map<string, string>());
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [observabilityErrors, setObservabilityErrors] = useState<ObservabilityErrorsResponse | null>(null);
  const [observabilityLoading, setObservabilityLoading] = useState(false);
  const [frontErrors] = useState<FrontendErrorEntry[]>([]);
  const [pathHealth, setPathHealth] = useState<PathHealthState>({});
  const [connectionTest, setConnectionTest] = useState<ConnectionTestState>({});
  const [reconnectBusy, setReconnectBusy] = useState(false);
  const reconnectBusyRef = useRef(reconnectBusy);
  reconnectBusyRef.current = reconnectBusy;
  const [pathCheckBusy, setPathCheckBusy] = useState(false);
  const [lastExportPath, setLastExportPath] = useState<string | null>(() => readPersistedExportPath());
  const [commLogInfo, setCommLogInfo] = useState<{ path: string | null }>(() => ({
    path: readPersistedCommLogPath(),
  }));
  const [healthPolling, setHealthPolling] = useState<PollingState>(DEFAULT_POLLING_STATE);
  const [statsPolling, setStatsPolling] = useState<PollingState>(DEFAULT_POLLING_STATE);
  const [dashboardLeaderState, setDashboardLeaderState] = useState<DashboardLeaderState | null>(null);
  const [pollingPausedByVisibility, setPollingPausedByVisibility] = useState(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      healthRequestSequenceRef.current++;
      pendingSpotServicesRef.current = null;
    };
  }, []);

  const applyCommLogInfoSnapshot = useCallback((next: CommLogInfo) => {
    setCommLogInfo(next);
    persistCommLogPath(next.path ?? null);
  }, []);

  const applyHealthSnapshot = useCallback((snapshot: HealthSnapshot, sentAtMs?: number, authoritative = false) => {
    if (!mountedRef.current) return false;
    const previousObservation = spotObservationRef.current;
    const decision = assessSpotObservation(snapshot, previousObservation, retiredSpotServicesRef.current, authoritative);
    if (!authoritative && decision.observation && previousObservation
      && decision.observation.serviceId !== previousObservation.serviceId) {
      decision.accepted = false;
      const serviceId = decision.observation.serviceId;
      if (!retiredSpotServicesRef.current.has(serviceId)
        && rejectedSpotServicesRef.current.get(serviceId) !== previousObservation.serviceId) {
        confirmSpotServiceRef.current?.(new Set([serviceId]));
      }
    }
    const { accepted, observation } = decision;
    // Advance ordering immediately; React may batch multiple received messages.
    if (accepted && observation) {
      if (authoritative) retiredSpotServicesRef.current.delete(observation.serviceId);
      if (previousObservation && previousObservation.serviceId !== observation.serviceId) {
        if (retiredSpotServicesRef.current.size >= SPOT_IDENTITY_HISTORY_LIMIT) {
          retiredSpotServicesRef.current.delete(retiredSpotServicesRef.current.values().next().value!);
        }
        retiredSpotServicesRef.current.add(previousObservation.serviceId);
      }
      spotObservationRef.current = observation;
    }
    const receipt = buildHealthReceipt(sentAtMs, Date.now(), performance.now());
    setHealthState(previous => mergeHealthSnapshot(previous, snapshot, receipt, decision));
    return accepted;
  }, []);

  const fetchHealthSnapshot = useCallback(async (timeoutMs?: number, caller: 'polling' | 'manual' = 'polling', mayApply?: () => boolean): Promise<HealthSnapshot | null | typeof SUPERSEDED_HEALTH_REQUEST> => {
    const sequence = ++healthRequestSequenceRef.current;
    const startedAt = performance.now();
    try {
      const data = await systemService.getHealth(timeoutMs);
      // The backend can capture ages before composing the rest of /health.
      // Carry the conservative request-duration upper bound in the payload so
      // followers receive it too, rather than losing it at broadcast sent_at.
      const delivered = includeHealthDeliveryAge(data, performance.now() - startedAt);
      if (!mountedRef.current || sequence !== healthRequestSequenceRef.current || mayApply?.() === false) {
        // Manual callers still own their successful response, even when a
        // newer request owns the dashboard state and polling broadcast.
        return caller === 'manual' ? delivered : SUPERSEDED_HEALTH_REQUEST;
      }
      const accepted = applyHealthSnapshot(delivered, undefined, true);
      return accepted || caller === 'manual' ? delivered : SUPERSEDED_HEALTH_REQUEST;
    } catch (error) {
      if (!mountedRef.current || sequence !== healthRequestSequenceRef.current || mayApply?.() === false) {
        return caller === 'manual' ? null : SUPERSEDED_HEALTH_REQUEST;
      }
      console.error('Failed to fetch health', error);
      return null;
    }
  }, [applyHealthSnapshot]);

  const pollHealthSnapshot = useCallback((timeoutMs?: number, mayApply?: () => boolean) =>
    fetchHealthSnapshot(timeoutMs, 'polling', mayApply), [fetchHealthSnapshot]);

  const fetchHealth = useCallback(async (timeoutMs?: number) => {
    const data = await fetchHealthSnapshot(timeoutMs, 'manual');
    return data === SUPERSEDED_HEALTH_REQUEST ? null : data;
  }, [fetchHealthSnapshot]);

  confirmSpotServiceRef.current = serviceIds => {
    if (!mountedRef.current || reconnectBusy || document.visibilityState === 'hidden') return;
    const currentServiceId = spotObservationRef.current?.serviceId;
    const candidates = new Set(Array.from(serviceIds).filter(serviceId => serviceId !== currentServiceId
      && !retiredSpotServicesRef.current.has(serviceId)
      && rejectedSpotServicesRef.current.get(serviceId) !== currentServiceId));
    if (!candidates.size) return;
    const pending = pendingSpotServicesRef.current;
    if (pending) {
      candidates.forEach(serviceId => {
        if (!pending.candidates.has(serviceId) && !pending.arriving.has(serviceId)) {
          if (pending.arriving.size >= SPOT_IDENTITY_HISTORY_LIMIT) pending.arriving.delete(pending.arriving.values().next().value!);
          pending.arriving.add(serviceId);
        }
      });
      return;
    }
    const confirmation = { candidates, arriving: new Set<string>() };
    pendingSpotServicesRef.current = confirmation;
    const mayApply = () => mountedRef.current && !reconnectBusyRef.current
      && document.visibilityState !== 'hidden' && pendingSpotServicesRef.current === confirmation;
    void fetchHealthSnapshot(undefined, 'polling', mayApply).then(data => {
      if (!mayApply()
        || !data || data === SUPERSEDED_HEALTH_REQUEST) return;
      const actual = spotObservationRef.current;
      if (!actual || data.spot_temperature?.spot_service_instance_id !== actual.serviceId) return;
      // This response can only disprove candidates known before its request.
      confirmation.candidates.forEach(candidate => {
        if (candidate !== actual.serviceId) rejectedSpotServicesRef.current.set(candidate, actual.serviceId);
      });
      const rejected = rejectedSpotServicesRef.current;
      while (rejected.size > 256) rejected.delete(rejected.keys().next().value!);
    }).finally(() => {
      if (pendingSpotServicesRef.current !== confirmation) return;
      pendingSpotServicesRef.current = null;
      if (confirmation.arriving.size) confirmSpotServiceRef.current?.(confirmation.arriving);
    });
  };

  const fetchStats = useCallback(async () => {
    try {
      const data = await systemService.getStats();
      setStats(data);
      return data;
    } catch (error) {
      console.error('Failed to fetch stats', error);
      return null;
    }
  }, []);

  const loadObservabilityErrors = useCallback(async () => {
    setObservabilityLoading(true);
    try {
      const data = await systemService.getObservabilityErrors(100);
      setObservabilityErrors(data);
    } catch (error) {
      console.error('Failed to load observability errors', error);
    } finally {
      setObservabilityLoading(false);
    }
  }, []);

  const clearObservabilityErrors = useCallback(async () => {
    try {
      await systemService.clearObservabilityErrors();
      await loadObservabilityErrors();
    } catch (error) {
      console.error('Failed to clear errors', error);
    }
  }, [loadObservabilityErrors]);

  const reconnect = useCallback(async () => {
    if (reconnectBusy) return false;
    setReconnectBusy(true);
    try {
      const res = await systemService.reconnect();
      return res.ok;
    } catch (error) {
      console.error('Reconnect failed', error);
      return false;
    } finally {
      setReconnectBusy(false);
    }
  }, [reconnectBusy]);

  const runConnectionTest = useCallback(async (payload: Record<string, unknown> = {}) => {
    try {
      const res = await systemService.runConnectionTest(payload);
      setConnectionTest((prev) => ({ ...prev, ...res.results }));
    } catch (error) {
      console.error('Connection test failed', error);
    }
  }, []);

  const checkPathHealth = useCallback(async (pathType: 'log' | 'snapshot', path: string) => {
    if (!path) return;
    setPathCheckBusy(true);
    try {
      const res = await systemService.checkPathHealth([{ key: pathType, path }]);
      if (res && res[pathType]) {
        setPathHealth((prev) => ({ ...prev, [pathType]: res[pathType] as PathHealthResult }));
      } else if (res) {
        setPathHealth((prev) => ({ ...prev, ...(res as PathHealthState) }));
      }
    } catch (error) {
      console.error(`Path check failed for ${pathType}`, error);
      setPathHealth((prev) => ({ ...prev, [pathType]: buildPathHealthFallback() }));
    } finally {
      setPathCheckBusy(false);
    }
  }, []);

  const checkPathsHealth = useCallback(async (items: { key: string; path: string }[]) => {
    return (await systemService.checkPathHealth(items)) as Record<string, unknown>;
  }, []);

  const createPath = useCallback(async (path: string) => {
    try {
      const res = await systemService.createPath(path);
      return Boolean(res?.ok);
    } catch (error) {
      console.error('Create path failed', error);
      throw error;
    }
  }, []);

  const browseFolder = useCallback(async (params?: { initial_dir?: string; title?: string }) => {
    try {
      const res = await systemService.browseFolder(params);
      if (res.ok && res.path) {
        return res.path;
      }
      return null;
    } catch (error) {
      console.error('Browse folder failed', error);
      return null;
    }
  }, []);

  const fetchLatestExportPath = useCallback(async () => {
    try {
      const res = await systemService.getLatestExportPath();
      const path = res.path ?? null;
      setLastExportPath(path);
      persistExportPath(path);
    } catch {
      // ignore
    }
  }, []);

  const exportObservability = useCallback(
    async (includeFrontendLogs = false) => {
      try {
        const res = await systemService.exportObservability({
          include_errors: true,
          front_errors: includeFrontendLogs ? frontErrors : [],
        });
        if (res.path) {
          setLastExportPath(res.path);
          persistExportPath(res.path);
          return res.path;
        }
        return null;
      } catch (error) {
        console.error('Export failed', error);
        throw error;
      }
    },
    [frontErrors]
  );

  const openExportFolder = useCallback(async () => {
    await systemService.openExportFolder();
  }, []);

  const openExportFile = useCallback(async () => {
    await systemService.openExportFile();
  }, []);

  const loadCommLogInfo = useCallback(async () => {
    try {
      return await systemService.getCommLogInfo();
    } catch (error) {
      console.error('Failed to fetch comm log info', error);
      return null;
    }
  }, []);

  const fetchCommLogInfo = useCallback(async () => {
    const data = await loadCommLogInfo();
    if (data) {
      applyCommLogInfoSnapshot(data);
    }
  }, [applyCommLogInfoSnapshot, loadCommLogInfo]);

  const openCommLogPath = useCallback(async () => {
    await systemService.openCommLogPath();
  }, []);

  const openCommLogFile = useCallback(async () => {
    await systemService.openCommLogFile();
  }, []);

  const saveSnapshot = useCallback(async (params: { image_base64: string; name: string; format: string }) => {
    try {
      await systemService.createSnapshot(params);
    } catch (error) {
      console.error('Snapshot save failed', error);
      throw error;
    }
  }, []);

  useSystemViewModelEffects({
    fetchHealth: pollHealthSnapshot,
    fetchStats,
    reconnectBusy,
    setHealthPolling,
    setStatsPolling,
    applyHealthSnapshot,
    applyStatsSnapshot: setStats,
    setDashboardLeaderState,
    setPollingPausedByVisibility,
  });

  return {
    health,
    healthReceipt,
    stats,
    observabilityErrors,
    frontErrors,
    pathHealth,
    connectionTest,
    reconnectBusy,
    pathCheckBusy,
    observabilityLoading,
    healthPolling,
    statsPolling,
    dashboardLeaderState,
    pollingPausedByVisibility,
    fetchHealth,
    fetchStats,
    loadObservabilityErrors,
    clearObservabilityErrors,
    reconnect,
    runConnectionTest,
    checkPathHealth,
    checkPathsHealth,
    createPath,
    browseFolder,
    setPathHealth,
    setPathCheckBusy,
    lastExportPath,
    loadCommLogInfo,
    applyCommLogInfoSnapshot,
    fetchLatestExportPath,
    exportObservability,
    openExportFolder,
    openExportFile,
    commLogInfo,
    fetchCommLogInfo,
    openCommLogPath,
    openCommLogFile,
    saveSnapshot,
  };
};
