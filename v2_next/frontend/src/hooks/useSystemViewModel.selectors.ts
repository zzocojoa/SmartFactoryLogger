import type { PathHealthResult } from '../types';

export const buildPathHealthFallback = (): PathHealthResult => ({
  status: 'UNKNOWN',
  exists: false,
  writable: false,
  is_dir: false,
  is_network: false,
  latency_ms: null,
  message: '경로 확인 실패',
  checked_at: Date.now(),
});
