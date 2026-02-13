import { apiClient } from '../client';
import type {
  BrowseFolderParams,
  BrowseFolderResponse,
  CommLogInfoResponse,
  ConnectionTestData,
  CreatePathResponse,
  LatestExportPathResponse,
  ObservabilityErrorsData,
  ObservabilityExportRequest,
  PathHealthRequestItem,
  PathHealthResponse,
  ReconnectResponse,
  SnapshotPayload,
  SystemHealthResponse,
  SystemStatsResponse,
} from '../systemService.types';

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
