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
});
