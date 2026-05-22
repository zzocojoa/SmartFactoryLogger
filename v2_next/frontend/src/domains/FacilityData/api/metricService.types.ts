import type { FactoryData } from '../../../shared/types';

export type LatestMetricResponse = FactoryData;

export interface MetricHistorySampleResponse {
  timestamp_ms: number;
  data: FactoryData;
}

export interface MetricHistoryResponse {
  samples: MetricHistorySampleResponse[];
  oldest_timestamp_ms: number | null;
  newest_timestamp_ms: number | null;
  history_instance_id: string;
  truncated: boolean;
}
