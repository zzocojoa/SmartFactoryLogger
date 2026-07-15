import { beforeEach, describe, expect, it, vi } from 'vitest';
import { STARTUP_POLL_REQUEST_TIMEOUT_MS } from '../pollingRequest';

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

  it('bounds the health request so startup retries cannot remain pending indefinitely', async () => {
    const health = { running: true };
    mocks.get.mockResolvedValueOnce({ data: health });

    await expect(fetchHealth()).resolves.toBe(health);
    expect(mocks.get).toHaveBeenCalledWith('/health', {
      timeout: STARTUP_POLL_REQUEST_TIMEOUT_MS,
    });
  });

  it('bounds the live-data request used by the polling worker', async () => {
    const data = { Status: 'Running', timestamp_ms: 1 };
    mocks.get.mockResolvedValueOnce({ data });

    await expect(fetchLatestMetric()).resolves.toBe(data);
    expect(mocks.get).toHaveBeenCalledWith('/api/data', {
      timeout: STARTUP_POLL_REQUEST_TIMEOUT_MS,
    });
  });
});
