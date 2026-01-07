import { apiClient } from './client';
import { FactoryData } from '../types';

export const metricService = {
  getLatest: async (): Promise<FactoryData> => {
    // App.tsx uses /api/data explicitly
    const response = await apiClient.get<FactoryData>('/api/data');
    return response.data;
  },
};
