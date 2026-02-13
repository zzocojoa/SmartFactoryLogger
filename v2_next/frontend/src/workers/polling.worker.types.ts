import type { FactoryData } from '../types';

export interface WorkerStartPayload {
  interval?: number;
}

export interface WorkerDataPayload {
  data: FactoryData;
  timestamp: number;
  latency: number;
}

export interface WorkerErrorPayload {
  message: string;
}

export type WorkerInboundMessage =
  | { type: 'START'; payload?: WorkerStartPayload }
  | { type: 'STOP'; payload?: undefined };

export type WorkerOutboundMessage =
  | { type: 'DATA'; payload: WorkerDataPayload }
  | { type: 'ERROR'; payload: WorkerErrorPayload };
