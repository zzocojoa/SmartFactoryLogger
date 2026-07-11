import type { SpotConfig } from '../../../shared/types';

export interface SpotImageResponseMetadata {
  source: string | null;
  captured_at: number | null;
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
