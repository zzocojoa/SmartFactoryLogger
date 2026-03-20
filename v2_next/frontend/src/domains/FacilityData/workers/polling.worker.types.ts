import type { FactoryData } from '../../../shared/types';

export interface WorkerStartPayload {
  interval?: number;
}

export interface WorkerDataPayload {
  data: FactoryData;
  timestamp: number;
  latency: number;
  poll_interval_ms: number;
  failure_count: number;
}

export interface WorkerErrorPayload {
  message: string;
  poll_interval_ms: number;
  failure_count: number;
}

export type WorkerInboundMessage =
  | { type: 'START'; payload?: WorkerStartPayload }
  | { type: 'STOP'; payload?: undefined };

export type WorkerOutboundMessage =
  | { type: 'DATA'; payload: WorkerDataPayload }
  | { type: 'ERROR'; payload: WorkerErrorPayload };
