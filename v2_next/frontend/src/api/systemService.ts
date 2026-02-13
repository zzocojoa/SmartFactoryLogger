import type {
  BrowseFolderParams,
  BrowseFolderResponse,
  CommLogInfoResponse,
  ConnectionTestData,
  CreatePathResponse,
  LatestExportPathResponse,
  ObservabilityExportRequest,
  PathHealthRequestItem,
  PathHealthResponse,
  ReconnectResponse,
  SnapshotPayload,
  SystemHealthResponse,
  SystemStatsResponse,
} from './systemService.types';
import {
  fetchCommLogInfo,
  fetchHealth,
  fetchLatestExportPath,
  fetchObservabilityErrors,
  fetchStats,
  postBrowseFolder,
  postClearObservabilityErrors,
  postConnectionTest,
  postCreatePath,
  postCreateSnapshot,
  postObservabilityExport,
  postOpenCommLogFile,
  postOpenCommLogPath,
  postOpenExportFile,
  postOpenExportFolder,
  postPathHealth,
  postReconnect,
} from './transport/systemService.transport';

export const systemService = {
  getHealth: (): Promise<SystemHealthResponse> => fetchHealth(),
  
  getStats: (): Promise<SystemStatsResponse> => fetchStats(),

  getObservabilityErrors: (limit: number) => fetchObservabilityErrors(limit),
  
  clearObservabilityErrors: postClearObservabilityErrors,

  getLatestExportPath: (): Promise<LatestExportPathResponse> => fetchLatestExportPath(),

  exportObservability: (params: ObservabilityExportRequest) => postObservabilityExport(params),

  openExportFile: postOpenExportFile,

  openExportFolder: postOpenExportFolder,
  
  reconnect: (): Promise<ReconnectResponse> => postReconnect(),
  
  createSnapshot: (params: SnapshotPayload) => postCreateSnapshot(params),

  getCommLogInfo: (): Promise<CommLogInfoResponse> => fetchCommLogInfo(),

  openCommLogPath: postOpenCommLogPath,

  openCommLogFile: postOpenCommLogFile,

  runConnectionTest: (payload: Record<string, unknown> = {}): Promise<ConnectionTestData> =>
    postConnectionTest(payload),

  checkPathHealth: (paths: PathHealthRequestItem[]): Promise<PathHealthResponse> => postPathHealth(paths),

  createPath: (path: string): Promise<CreatePathResponse> => postCreatePath(path),

  browseFolder: (params?: BrowseFolderParams): Promise<BrowseFolderResponse> =>
    postBrowseFolder(params),
};
