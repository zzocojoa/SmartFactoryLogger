import type { LatestMetricResponse } from './metricService.types';
import { fetchLatestMetric } from './transport/metricService.transport';

export const metricService = {
  getLatest: async (): Promise<LatestMetricResponse> => fetchLatestMetric(),
};
