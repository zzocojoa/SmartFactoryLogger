import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('../client', () => ({
  apiClient: {
    post: mocks.post,
  },
}));

import { postConnectionTest } from './systemService.transport';

describe('connection-test transport', () => {
  beforeEach(() => {
    mocks.post.mockReset();
    delete window.smartFactoryElectron;
  });

  it('uses the trusted Electron bridge when available', async () => {
    const result = { results: { spot: { ok: true } } };
    const testConnection = vi.fn().mockResolvedValue(result);
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: vi.fn(),
      testConnection,
    };

    await expect(postConnectionTest({ spot: { url: 'http://spot.invalid' } }))
      .resolves.toBe(result);
    expect(testConnection).toHaveBeenCalledWith({
      spot: { url: 'http://spot.invalid' },
    });
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('uses the HTTP endpoint outside Electron development', async () => {
    const result = { results: { spot: { ok: true } } };
    mocks.post.mockResolvedValueOnce({ data: result });

    await expect(postConnectionTest({})).resolves.toBe(result);
    expect(mocks.post).toHaveBeenCalledWith('/api/control/test-connection', {});
  });
});
