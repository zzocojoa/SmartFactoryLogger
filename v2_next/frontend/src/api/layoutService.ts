import { apiClient } from './client';

export const layoutService = {
  getLayouts: async () => {
    const response = await apiClient.get('/api/layouts');
    return response.data;
  },
  
  saveLayout: async (payload: any) => {
    const response = await apiClient.post('/api/layouts', payload);
    return response.data;
  },

  getLayoutSnapshot: async () => {
    const response = await apiClient.get('/api/layout');
    return response.data;
  },

  restoreLayout: async (slotId: string) => {
    const response = await apiClient.post('/api/layouts/restore', { slot_id: slotId });
    return response.data;
  },

  deleteLayout: async (slotId: string) => {
    const response = await apiClient.post('/api/layouts/delete', { slot_id: slotId });
    return response.data;
  }
};
