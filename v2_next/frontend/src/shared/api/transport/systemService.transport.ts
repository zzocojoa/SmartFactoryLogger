import { apiClient } from '../client';
import type {
  BrowseFolderParams,
  BrowseFolderResponse,
  CommLogInfoResponse,
  ConnectionTestData,
  CreatePathResponse,
  LatestExportPathResponse,
  MemoryDetailsData,
  MemoryExportRequest,
  MemoryStateData,
  ObservabilityErrorsData,
  ObservabilityExportRequest,
  PathHealthRequestItem,
  PathHealthResponse,
  ReconnectResponse,
  SnapshotPayload,
  SystemHealthResponse,
  SystemStatsResponse,
} from '../../../domains/Observability/api/systemService.types';

export const fetchHealth = async (): Promise<SystemHealthResponse> => {
  const response = await apiClient.get<SystemHealthResponse>('/health');
  return response.data;
};

export const fetchStats = async (): Promise<SystemStatsResponse> => {
  const response = await apiClient.get<SystemStatsResponse>('/stats');
  return response.data;
};

export const fetchObservabilityErrors = async (limit: number): Promise<ObservabilityErrorsData> => {
  const response = await apiClient.get<ObservabilityErrorsData>('/api/observability/errors', {
    params: { limit },
  });
  return response.data;
};

export const fetchMemoryState = async (): Promise<MemoryStateData> => {
  const response = await apiClient.get<MemoryStateData>('/api/memory/state');
  return response.data;
};

export const fetchMemoryDetails = async (): Promise<MemoryDetailsData> => {
  const response = await apiClient.get<MemoryDetailsData>('/api/memory/details');
  return response.data;
};

export const postClearObservabilityErrors = async () => {
  const response = await apiClient.post('/api/observability/errors/clear');
  return response.data;
};

export const fetchLatestExportPath = async (): Promise<LatestExportPathResponse> => {
  const response = await apiClient.get<LatestExportPathResponse>('/api/observability/export/latest');
  return response.data;
};

export const postObservabilityExport = async (params: ObservabilityExportRequest) => {
  const response = await apiClient.post<{ path?: string }>('/api/observability/export', params);
  return response.data;
};

export const fetchLatestMemoryExportPath = async (): Promise<LatestExportPathResponse> => {
  const response = await apiClient.get<LatestExportPathResponse>('/api/memory/export/latest');
  return response.data;
};

export const postStartMemoryProfiler = async () => {
  const response = await apiClient.post('/api/memory/profiler/start');
  return response.data;
};

export const postStopMemoryProfiler = async () => {
  const response = await apiClient.post('/api/memory/profiler/stop');
  return response.data;
};

export const postCaptureMemorySnapshot = async () => {
  const response = await apiClient.post('/api/memory/snapshot');
  return response.data;
};

export const postMemoryExport = async (params: MemoryExportRequest) => {
  const response = await apiClient.post<{ path?: string }>('/api/memory/export', params);
  return response.data;
};

export const postOpenMemoryExportFile = async () => apiClient.post('/api/memory/export/open-file');

export const postOpenMemoryExportFolder = async () => apiClient.post('/api/memory/export/open-folder');

export const postOpenExportFile = async () => apiClient.post('/api/observability/export/open-file');

export const postOpenExportFolder = async () => apiClient.post('/api/observability/export/open-folder');

export const postReconnect = async (): Promise<ReconnectResponse> => {
  const response = await apiClient.post<ReconnectResponse>('/api/control/reconnect');
  return response.data;
};

export const postCreateSnapshot = async (params: SnapshotPayload) =>
  apiClient.post('/api/control/snapshot', params);

export const fetchCommLogInfo = async (): Promise<CommLogInfoResponse> => {
  const response = await apiClient.get<CommLogInfoResponse>('/api/logs/comm-metrics');
  return response.data;
};

export const postOpenCommLogPath = async () => apiClient.post('/api/logs/comm-metrics/open');

export const postOpenCommLogFile = async () => apiClient.post('/api/logs/comm-metrics/open-file');

export const postConnectionTest = async (
  payload: Record<string, unknown> = {}
): Promise<ConnectionTestData> => {
  const response = await apiClient.post<ConnectionTestData>('/api/control/test-connection', payload);
  return response.data;
};

export const postPathHealth = async (paths: PathHealthRequestItem[]): Promise<PathHealthResponse> => {
  const response = await apiClient.post<PathHealthResponse>('/api/control/path-health', { paths });
  return response.data;
};

export const postCreatePath = async (path: string): Promise<CreatePathResponse> => {
  const response = await apiClient.post<CreatePathResponse>('/api/control/path-create', { path });
  return response.data;
};

export const postBrowseFolder = async (
  params?: BrowseFolderParams
): Promise<BrowseFolderResponse> => {
  const response = await apiClient.post<BrowseFolderResponse>(
    '/api/control/folder-browse',
    params || {}
  );
  return response.data;
};
