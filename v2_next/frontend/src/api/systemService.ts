import { apiClient } from './client';

export const systemService = {
  getHealth: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },
  
  getStats: async () => {
    const response = await apiClient.get('/stats');
    return response.data;
  },

  getObservabilityErrors: async (limit: number) => {
    const response = await apiClient.get('/api/observability/errors', { params: { limit } });
    return response.data;
  },
  
  clearObservabilityErrors: async () => {
    const response = await apiClient.post('/api/observability/errors/clear');
    return response.data;
  },

  getLatestExportPath: async () => {
    const response = await apiClient.get<{ path: string | null }>('/api/observability/export/latest');
    return response.data;
  },

  exportObservability: async (params: { include_errors: boolean; front_errors: any[] }) => {
    const response = await apiClient.post<{ path?: string }>('/api/observability/export', params);
    return response.data;
  },

  openExportFile: async () => {
    return await apiClient.post('/api/observability/export/open-file');
  },

  openExportFolder: async () => {
    return await apiClient.post('/api/observability/export/open-folder');
  },
  
  reconnect: async () => {
    return await apiClient.post('/api/control/reconnect');
  },
  
  createSnapshot: async (params: { image_base64: string; name: string; format: string }) => {
    return await apiClient.post('/api/control/snapshot', params);
  },

  getCommLogInfo: async () => {
    const response = await apiClient.get('/api/logs/comm-metrics');
    return response.data;
  },

  openCommLogPath: async () => {
    return await apiClient.post('/api/logs/comm-metrics/open');
  },

  openCommLogFile: async () => {
    return await apiClient.post('/api/logs/comm-metrics/open-file');
  },

  runConnectionTest: async (payload: any) => {
    const response = await apiClient.post('/api/control/test-connection', payload);
    return response.data;
  },

  checkPathHealth: async (paths: { key: string; path: string }[]) => {
    const response = await apiClient.post('/api/control/path-health', { paths });
    return response.data;
  },

  createPath: async (path: string) => {
    return await apiClient.post('/api/control/path-create', { path });
  }
};
