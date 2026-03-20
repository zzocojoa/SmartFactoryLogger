import { useState, useCallback } from 'react';
import { systemService } from '../api/systemService';
import type {
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
import { persistExportPath, readPersistedExportPath } from './useSystemViewModel.service';
import { useSystemViewModelEffects } from './useSystemViewModelEffects';
import type { PollingState, UseSystemViewModel } from './useSystemViewModel.types';

const DEFAULT_POLLING_STATE: PollingState = {
  degraded: false,
  intervalMs: 5000,
  failureCount: 0,
};

export const useSystemViewModel = (): UseSystemViewModel => {
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [observabilityErrors, setObservabilityErrors] = useState<ObservabilityErrorsResponse | null>(null);
  const [observabilityLoading, setObservabilityLoading] = useState(false);
  const [frontErrors] = useState<FrontendErrorEntry[]>([]);
  const [pathHealth, setPathHealth] = useState<PathHealthState>({});
  const [connectionTest, setConnectionTest] = useState<ConnectionTestState>({});
  const [reconnectBusy, setReconnectBusy] = useState(false);
  const [pathCheckBusy, setPathCheckBusy] = useState(false);
  const [lastExportPath, setLastExportPath] = useState<string | null>(() => readPersistedExportPath());
  const [commLogInfo, setCommLogInfo] = useState<{ path: string | null }>({ path: null });
  const [healthPolling, setHealthPolling] = useState<PollingState>(DEFAULT_POLLING_STATE);
  const [statsPolling, setStatsPolling] = useState<PollingState>(DEFAULT_POLLING_STATE);
  const [dashboardLeaderState, setDashboardLeaderState] = useState<DashboardLeaderState | null>(null);
  const [pollingPausedByVisibility, setPollingPausedByVisibility] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await systemService.getHealth();
      setHealth(data);
      return data;
    } catch (error) {
      console.error('Failed to fetch health', error);
      return null;
    }
  }, []);

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
      setConnectionTest(res.results);
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

  const fetchCommLogInfo = useCallback(async () => {
    try {
      const data = await systemService.getCommLogInfo();
      setCommLogInfo(data);
    } catch (error) {
      console.error('Failed to fetch comm log info', error);
    }
  }, []);

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
    fetchHealth,
    fetchStats,
    reconnectBusy,
    setHealthPolling,
    setStatsPolling,
    applyHealthSnapshot: setHealth,
    applyStatsSnapshot: setStats,
    setDashboardLeaderState,
    setPollingPausedByVisibility,
  });

  return {
    health,
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
