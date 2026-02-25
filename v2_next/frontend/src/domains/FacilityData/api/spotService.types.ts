import type { SpotConfig } from '../../../shared/types';

export interface SpotControlPayload {
  action: string;
  value?: number;
}

export interface SpotActuatorPayload {
  step: number;
}

export type SpotConfigResponse = SpotConfig;
