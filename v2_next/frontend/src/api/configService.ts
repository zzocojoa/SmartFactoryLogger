import { apiClient } from './client';

export const configService = {
  getConfig: async () => {
    const response = await apiClient.get('/api/config');
    return response.data;
  },

  saveConfig: async (config: any) => {
    const response = await apiClient.post('/api/config', config);
    return response.data;
  },

  getNotice: async () => {
    const response = await apiClient.get('/api/config/notice');
    return response.data;
  },

  saveNotice: async (content: string) => {
    const response = await apiClient.post('/api/config/notice', { content });
    return response.data;
  },
  
  testConnection: async (target: string, params: any) => {
    const response = await apiClient.post(`/api/config/test/${target}`, params);
    return response.data;
  },

  getCentralStatus: async () => {
    const response = await apiClient.get('/api/config/central-status');
    return response.data;
  },

  syncCentral: async () => {
    const response = await apiClient.post('/api/config/sync');
    return response.data;
  },

  restoreDefaults: async () => {
    return await apiClient.post('/api/config/restore-defaults');
  },

  restoreBackup: async () => {
    return await apiClient.post('/api/config/restore-backup');
  },

  applyPending: async () => {
    return await apiClient.post('/api/config/pending/apply');
  },

  clearPending: async () => {
    return await apiClient.post('/api/config/pending/clear');
  },

  toggleOverride: async (params: { enabled: boolean; password?: string; actor: string }) => {
    const response = await apiClient.post('/api/config/override', params);
    return response.data;
  }
};
