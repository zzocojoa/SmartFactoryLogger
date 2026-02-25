import { metricService } from '../../api/metricService';

export const fetchLatestMetricWithLatency = async () => {
  const t0 = performance.now();
  const data = await metricService.getLatest();
  const t1 = performance.now();
  return {
    data,
    latency: t1 - t0,
    timestamp: Date.now(),
  };
};
