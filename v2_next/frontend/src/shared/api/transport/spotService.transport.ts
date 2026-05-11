import { apiClient } from '../client';
import type {
  SpotActuatorPayload,
  SpotConfigResponse,
  SpotControlPayload,
} from '../../../domains/FacilityData/api/spotService.types';

export interface SpotFocusResponse {
  status: string;
  current?: number;
  new?: number;
  verified?: number;
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

const isOptionalNumber = (value: unknown): value is number | undefined => {
  return value === undefined || (typeof value === 'number' && Number.isFinite(value));
};

const isOptionalString = (value: unknown): value is string | undefined => {
  return value === undefined || typeof value === 'string';
};

const isSpotFocusResponse = (data: unknown): data is SpotFocusResponse => {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const candidate = data as {
    status?: unknown;
    current?: unknown;
    new?: unknown;
    verified?: unknown;
    request_steps?: unknown;
    focus_step?: unknown;
    message?: unknown;
  };
  return (
    typeof candidate.status === 'string' &&
    isOptionalNumber(candidate.current) &&
    isOptionalNumber(candidate.new) &&
    isOptionalNumber(candidate.verified) &&
    isOptionalNumber(candidate.request_steps) &&
    isOptionalNumber(candidate.focus_step) &&
    isOptionalString(candidate.message)
  );
};

const buildSpotFocusInvalidResponseError = (steps: number, data: unknown): Error => {
  return new Error(
    `SPOT focus response invalid; endpoint=/api/spot/focus; steps=${steps}; response=${formatErrorResponseData(data).slice(0, 500)}`
  );
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

const buildSpotActuatorError = (step: number, error: unknown): Error => {
  if (!isApiErrorCandidate(error)) {
    return new Error(`SPOT actuator request failed; endpoint=/api/spot/actuator; step=${step}; error=${String(error)}`);
  }

  const status = error.response?.status;
  const responseData = error.response ? formatErrorResponseData(error.response.data) : null;
  const causeMessage = error.message?.trim() || error.constructor.name;
  const responseContext = responseData === null ? '' : `; response=${responseData.slice(0, 500)}`;
  const statusContext = status === undefined ? '' : `; status=${status}`;

  return new Error(
    `SPOT actuator request failed; endpoint=/api/spot/actuator; step=${step}${statusContext}; error=${causeMessage}${responseContext}`
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
    const response = await apiClient.post<unknown>('/api/spot/focus', null, { params: { steps } });
    if (!isSpotFocusResponse(response.data)) {
      throw buildSpotFocusInvalidResponseError(steps, response.data);
    }
    return response.data;
  } catch (error) {
    throw buildSpotFocusError(steps, error);
  }
};

export const postSpotActuator = async (payload: SpotActuatorPayload): Promise<unknown> => {
  try {
    const response = await apiClient.post<unknown>('/api/spot/actuator', payload);
    return response.data;
  } catch (error) {
    throw buildSpotActuatorError(payload.step, error);
  }
};
