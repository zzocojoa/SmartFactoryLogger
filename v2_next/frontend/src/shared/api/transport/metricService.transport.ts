import { apiClient } from '../client';
import type {
  LatestMetricResponse,
  MetricHistoryResponse,
} from '../../../domains/FacilityData/api/metricService.types';

const HISTORY_BACKFILL_LIMIT = 20_000;

export const fetchLatestMetric = async (): Promise<LatestMetricResponse> => {
  const response = await apiClient.get<LatestMetricResponse>('/api/data');
  return response.data;
};

export const fetchMetricHistorySince = async (sinceMs: number): Promise<MetricHistoryResponse> => {
  const response = await apiClient.get<MetricHistoryResponse>('/api/data/history', {
    params: {
      since_ms: sinceMs,
      limit: HISTORY_BACKFILL_LIMIT,
    },
  });
  return response.data;
};
