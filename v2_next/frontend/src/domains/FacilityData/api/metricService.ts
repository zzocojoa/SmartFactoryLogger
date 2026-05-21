import type { LatestMetricResponse, MetricHistoryResponse } from './metricService.types';
import { fetchLatestMetric, fetchMetricHistorySince } from '../../../shared/api/transport/metricService.transport';

export const metricService = {
  getLatest: async (): Promise<LatestMetricResponse> => fetchLatestMetric(),
  getHistorySince: async (sinceMs: number): Promise<MetricHistoryResponse> => fetchMetricHistorySince(sinceMs),
};
