import { apiClient } from '../client';
import type {
  SpotActuatorPayload,
  SpotConfigResponse,
  SpotControlPayload,
} from '../../../domains/FacilityData/api/spotService.types';

interface SpotFocusResponse {
  status: string;
  current?: number;
  new?: number;
  request_steps?: number;
  focus_step?: number;
  message?: string;
}

interface ApiErrorResponse {
  status?: number;
  data?: unknown;
}

interface ApiErrorCandidate {
  message?: string;
  response?: ApiErrorResponse;
}

const isApiErrorCandidate = (error: unknown): error is ApiErrorCandidate => {
  return Boolean(error) && typeof error === 'object';
};

const formatErrorResponseData = (data: unknown): string => {
  if (typeof data === 'string') {
    return data;
  }
  try {
    return JSON.stringify(data);
  } catch {
    return String(data);
  }
};

const buildSpotFocusError = (steps: number, error: unknown): Error => {
  if (!isApiErrorCandidate(error)) {
    return new Error(`SPOT focus request failed; endpoint=/api/spot/focus; steps=${steps}; error=${String(error)}`);
  }

  const status = error.response?.status;
  const responseData = error.response ? formatErrorResponseData(error.response.data) : null;
  const causeMessage = error.message?.trim() || error.constructor.name;
  const responseContext = responseData === null ? '' : `; response=${responseData.slice(0, 500)}`;
  const statusContext = status === undefined ? '' : `; status=${status}`;

  return new Error(
    `SPOT focus request failed; endpoint=/api/spot/focus; steps=${steps}${statusContext}; error=${causeMessage}${responseContext}`
  );
};

export const fetchSpotConfig = async (): Promise<SpotConfigResponse> => {
  const response = await apiClient.get<SpotConfigResponse>('/api/spot/config');
  return response.data;
};

export const postSpotControl = async (params: SpotControlPayload) => {
  const response = await apiClient.post('/api/spot/control', params);
  return response.data;
};

export const postSpotFocus = async (steps: number): Promise<SpotFocusResponse> => {
  try {
    const response = await apiClient.post<SpotFocusResponse>('/api/spot/focus', null, { params: { steps } });
    return response.data;
  } catch (error) {
    throw buildSpotFocusError(steps, error);
  }
};

export const postSpotActuator = async (payload: SpotActuatorPayload) => {
  const response = await apiClient.post('/api/spot/actuator', payload);
  return response.data;
};
