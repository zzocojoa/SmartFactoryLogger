import type {
  ConnectionTestState,
  FrontendErrorEntry,
  HealthSnapshot,
  ObservabilityErrorsResponse,
  PathHealthState,
  StatsSnapshot,
} from '../types';
import type { Dispatch, SetStateAction } from 'react';

export interface UseSystemViewModel {
  health: HealthSnapshot | null;
  stats: StatsSnapshot | null;
  observabilityErrors: ObservabilityErrorsResponse | null;
  frontErrors: FrontendErrorEntry[];
  pathHealth: PathHealthState;
  connectionTest: ConnectionTestState;
  reconnectBusy: boolean;
  pathCheckBusy: boolean;
  observabilityLoading: boolean;
  fetchHealth: () => Promise<HealthSnapshot | null>;
  fetchStats: () => Promise<StatsSnapshot | null>;
  loadObservabilityErrors: () => Promise<void>;
  clearObservabilityErrors: () => Promise<void>;
  reconnect: () => Promise<boolean>;
  runConnectionTest: (payload?: Record<string, unknown>) => Promise<void>;
  checkPathHealth: (pathType: 'log' | 'snapshot', path: string) => Promise<void>;
  checkPathsHealth: (items: { key: string; path: string }[]) => Promise<Record<string, unknown>>;
  createPath: (path: string) => Promise<boolean>;
  browseFolder: (params?: { initial_dir?: string; title?: string }) => Promise<string | null>;
  setPathHealth: Dispatch<SetStateAction<PathHealthState>>;
  setPathCheckBusy: Dispatch<SetStateAction<boolean>>;
  lastExportPath: string | null;
  fetchLatestExportPath: () => Promise<void>;
  exportObservability: (includeFrontendLogs?: boolean) => Promise<string | null>;
  openExportFolder: () => Promise<void>;
  openExportFile: () => Promise<void>;
  commLogInfo: { path: string | null };
  fetchCommLogInfo: () => Promise<void>;
  openCommLogPath: () => Promise<void>;
  openCommLogFile: () => Promise<void>;
  saveSnapshot: (params: { image_base64: string; name: string; format: string }) => Promise<void>;
}
