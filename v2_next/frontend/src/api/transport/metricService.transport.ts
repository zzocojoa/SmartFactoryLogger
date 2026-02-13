import { apiClient } from '../client';
import type { LatestMetricResponse } from '../metricService.types';

export const fetchLatestMetric = async (): Promise<LatestMetricResponse> => {
  const response = await apiClient.get<LatestMetricResponse>('/api/data');
  return response.data;
};
