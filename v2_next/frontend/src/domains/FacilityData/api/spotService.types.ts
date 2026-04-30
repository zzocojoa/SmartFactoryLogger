import type { SpotConfig } from '../../../shared/types';

export type SpotImageHeaderStatus = 'ok' | 'fresh' | 'stale' | 'backoff' | 'error' | 'empty' | 'unknown';

export interface SpotImageResponseMetadata {
  status: SpotImageHeaderStatus;
  raw_status: string | null;
  cache_status: SpotImageHeaderStatus;
  raw_cache_status: string | null;
  proxy_state: SpotImageHeaderStatus;
  raw_proxy_state: string | null;
  source: string | null;
  age_sec: number | null;
  max_stale_age_sec: number | null;
  captured_at: number | null;
  retry_after_sec: number | null;
  received_at: number;
  latency_ms: number;
}

export interface SpotControlPayload {
  action: string;
  value?: number;
}

export interface SpotActuatorPayload {
  step: number;
}

export type SpotConfigResponse = SpotConfig;
