import type {
  WorkerDataPayload,
  WorkerErrorPayload,
  WorkerOutboundMessage,
} from './polling.worker.types';

export const toDataMessage = (payload: WorkerDataPayload): WorkerOutboundMessage => ({
  type: 'DATA',
  payload,
});

export const toErrorMessage = (payload: WorkerErrorPayload): WorkerOutboundMessage => ({
  type: 'ERROR',
  payload,
});
