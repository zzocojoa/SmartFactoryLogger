import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  POLL_REQUEST_TIMEOUT_MS,
  STARTUP_HEALTH_REQUEST_TIMEOUT_MS,
} from '../pollingRequest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../client', () => ({
  apiClient: {
    get: mocks.get,
  },
}));

import { fetchLatestMetric } from './metricService.transport';
import { fetchHealth } from './systemService.transport';
import { fetchMetricHistorySinceOnMainThreadWithLatency } from '../../../domains/FacilityData/hooks/useMetricsViewModel.service';

describe('startup polling transport', () => {
  beforeEach(() => {
    mocks.get.mockReset();
  });

  it('uses the startup-specific timeout when the health caller requests it', async () => {
    const health = { running: true };
    mocks.get.mockResolvedValueOnce({ data: health });

    await expect(fetchHealth(STARTUP_HEALTH_REQUEST_TIMEOUT_MS)).resolves.toBe(health);
    expect(mocks.get).toHaveBeenCalledWith('/health', {
      timeout: STARTUP_HEALTH_REQUEST_TIMEOUT_MS,
    });
  });

  it('returns health requests to the steady polling timeout by default', async () => {
    const health = { running: true };
    mocks.get.mockResolvedValueOnce({ data: health });

    await expect(fetchHealth()).resolves.toBe(health);
    expect(mocks.get).toHaveBeenCalledWith('/health', {
      timeout: POLL_REQUEST_TIMEOUT_MS,
    });
  });

  it('bounds the live-data request used by the polling worker', async () => {
    const data = { Status: 'Running', timestamp_ms: 1 };
    mocks.get.mockResolvedValueOnce({ data });

    await expect(fetchLatestMetric()).resolves.toBe(data);
    expect(mocks.get).toHaveBeenCalledWith('/api/data', {
      timeout: POLL_REQUEST_TIMEOUT_MS,
    });
  });

  it('passes the history cursor through the production service and transport chain', async () => {
    const cursor = `${'a'.repeat(32)}:42`;
    const response = { samples: [], next_cursor: cursor };
    mocks.get.mockResolvedValueOnce({ data: response });
    const actual = await fetchMetricHistorySinceOnMainThreadWithLatency(60_000, cursor);
    expect(actual.data).toBe(response);
    expect(mocks.get).toHaveBeenCalledWith('/api/data/history', {
      params: { since_ms: 60_000, limit: 20_000, cursor },
    });
  });
});
