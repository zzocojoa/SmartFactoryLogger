import type { SpotConfig } from '../../../shared/types';

export interface SpotImageResponseMetadata {
  source: string | null;
  captured_at: number | null;
  age_ms?: number | null;
  image_upstream_suppressed?: boolean | null;
  suppression_reason?: 'storage_pressure' | null;
  retry_after_sec?: number | null;
  internal_temperature?: number | null;
  internal_temperature_at?: number | null;
  internal_temperature_status?: string | null;
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
