import { useState, useCallback, useEffect, useRef } from 'react';
import { systemService } from '../api/systemService';
import {
  HealthSnapshot,
  StatsSnapshot,
  ObservabilityErrorsResponse,
  PathHealthState,
  ConnectionTestState,
  FrontendErrorEntry,
  ObservabilityErrorItem,
  PathHealthResult
} from '../types';
import { EXPORT_PATH_STORAGE_KEY } from '../constants/logic';

export interface UseSystemViewModel {
  health: HealthSnapshot | null;
  stats: StatsSnapshot | null;
  observabilityErrors: ObservabilityErrorsResponse | null;
  frontErrors: FrontendErrorEntry[];
  pathHealth: PathHealthState;
  connectionTest: ConnectionTestState;
  
  // Loading/Busy States
  reconnectBusy: boolean;
  pathCheckBusy: boolean;
  observabilityLoading: boolean;
  
  // Actions
  fetchHealth: () => Promise<HealthSnapshot | null>;
  fetchStats: () => Promise<StatsSnapshot | null>;
  loadObservabilityErrors: () => Promise<void>;
  clearObservabilityErrors: () => Promise<void>;
  reconnect: () => Promise<boolean>;
  runConnectionTest: (payload?: any) => Promise<void>;
  
  // Path Health
  checkPathHealth: (pathType: 'log' | 'snapshot', path: string) => Promise<void>;
  checkPathsHealth: (items: { key: string; path: string }[]) => Promise<any>;
  createPath: (path: string) => Promise<boolean>;
  setPathHealth: React.Dispatch<React.SetStateAction<PathHealthState>>; // Expose setter for complex merge logic in View
  setPathCheckBusy: React.Dispatch<React.SetStateAction<boolean>>;
  
  // Observability Export
  lastExportPath: string | null;
  fetchLatestExportPath: () => Promise<void>;
  exportObservability: (includeFrontendLogs?: boolean) => Promise<string | null>;
  openExportFolder: () => Promise<void>;
  openExportFile: () => Promise<void>;

  // Comm Log
  commLogInfo: { path: string | null };
  fetchCommLogInfo: () => Promise<void>;
  openCommLogPath: () => Promise<void>;
  openCommLogFile: () => Promise<void>;

  // Snapshot
  saveSnapshot: (params: { image_base64: string; name: string; format: string }) => Promise<void>;
}

export const useSystemViewModel = (): UseSystemViewModel => {
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [observabilityErrors, setObservabilityErrors] = useState<ObservabilityErrorsResponse | null>(null);
  const [observabilityLoading, setObservabilityLoading] = useState(false);
  const [frontErrors, setFrontErrors] = useState<FrontendErrorEntry[]>([]); 
  
  const [pathHealth, setPathHealth] = useState<PathHealthState>({});
  const [connectionTest, setConnectionTest] = useState<ConnectionTestState>({});
  
  const [reconnectBusy, setReconnectBusy] = useState(false);
  const [pathCheckBusy, setPathCheckBusy] = useState(false);
  
  const [lastExportPath, setLastExportPath] = useState<string | null>(null);
  const [commLogInfo, setCommLogInfo] = useState<{ path: string | null }>({ path: null });

  // Persistence Helper
  const persistExportPath = useCallback((path: string | null) => {
    if (typeof window === 'undefined') return;
    try {
      if (path) {
        window.localStorage.setItem(EXPORT_PATH_STORAGE_KEY, path);
      } else {
        window.localStorage.removeItem(EXPORT_PATH_STORAGE_KEY);
      }
    } catch (error) {
      console.error('Export path save failed', error);
    }
  }, []);

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
          loadObservabilityErrors();
      } catch (error) {
          console.error("Failed to clear errors", error);
      }
  }, [loadObservabilityErrors]);

  const reconnect = useCallback(async () => {
    if (reconnectBusy) return false;
    setReconnectBusy(true);
    try {
      const res = await systemService.reconnect();
      return (res as any).ok; 
    } catch (error) {
      console.error('Reconnect failed', error);
      return false;
    } finally {
      setReconnectBusy(false);
    }
  }, [reconnectBusy]);

  const runConnectionTest = useCallback(async (payload: any = {}) => {
      try {
          const res = await systemService.runConnectionTest(payload);
          setConnectionTest(res.results as any);
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
             setPathHealth(prev => ({ ...prev, [pathType]: res[pathType] }));
          } else if (res) {
             setPathHealth(prev => ({ ...prev, ...res }));
          }
      } catch (error) {
         console.error(`Path check failed for ${pathType}`, error);
         setPathHealth(prev => ({ 
             ...prev, 
             [pathType]: { 
                 status: 'UNKNOWN', 
                 exists: false, 
                 writable: false, 
                 is_dir: false, 
                 is_network: false, 
                 latency_ms: null, 
                 message: '검사 실패', 
                 checked_at: Date.now() 
             } as PathHealthResult 
         }));
      } finally {
          setPathCheckBusy(false);
      }
  }, []);

  const checkPathsHealth = useCallback(async (items: { key: string; path: string }[]) => {
      return await systemService.checkPathHealth(items);
  }, []);

  const createPath = useCallback(async (path: string) => {
      try {
          const res = await systemService.createPath(path);
          return (res && (res as any).ok);
      } catch (error) {
          console.error('Create path failed', error);
          throw error;
      }
  }, []);

  const fetchLatestExportPath = useCallback(async () => {
      try {
          const res = await systemService.getLatestExportPath();
          const path = res.path ?? null;
          setLastExportPath(path);
          persistExportPath(path);
      } catch (error) {
          // ignore
      }
  }, [persistExportPath]);

  const exportObservability = useCallback(async (includeFrontendLogs = false) => {
      try {
          const res = await systemService.exportObservability({ 
            include_errors: true, 
            front_errors: includeFrontendLogs ? frontErrors : [] 
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
  }, [frontErrors, persistExportPath]);
  
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
    
    fetchHealth,
    fetchStats,
    loadObservabilityErrors,
    clearObservabilityErrors,
    reconnect,
    runConnectionTest,
    checkPathHealth,
    checkPathsHealth,
    createPath,
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
    
    saveSnapshot
  };
};
