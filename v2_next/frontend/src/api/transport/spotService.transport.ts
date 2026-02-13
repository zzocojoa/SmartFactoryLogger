import { apiClient } from '../client';
import type {
  SpotActuatorPayload,
  SpotConfigResponse,
  SpotControlPayload,
} from '../spotService.types';

export const fetchSpotConfig = async (): Promise<SpotConfigResponse> => {
  const response = await apiClient.get<SpotConfigResponse>('/api/spot/config');
  return response.data;
};

export const postSpotControl = async (params: SpotControlPayload) => {
  const response = await apiClient.post('/api/spot/control', params);
  return response.data;
};

export const postSpotFocus = async (steps: number) => {
  const response = await apiClient.post('/api/spot/focus', null, { params: { steps } });
  return response.data;
};

export const postSpotActuator = async (payload: SpotActuatorPayload) => {
  const response = await apiClient.post('/api/spot/actuator', payload);
  return response.data;
};
