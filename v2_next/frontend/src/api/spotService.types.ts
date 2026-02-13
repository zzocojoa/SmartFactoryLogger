import type { SpotConfig } from '../types';

export interface SpotControlPayload {
  action: string;
  value?: number;
}

export interface SpotActuatorPayload {
  step: number;
}

export type SpotConfigResponse = SpotConfig;
