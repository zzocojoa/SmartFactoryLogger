import { apiClient } from '../client';
import type {
  ClientLayoutListItem,
  ClientLayoutSavePayload,
  LayoutSavePayload,
  LayoutSlotActionPayload,
} from '../../../domains/Configuration/api/layoutService.types';
import type { LayoutSnapshot } from '../../types';

export const fetchLayouts = async () => {
  const response = await apiClient.get('/api/layouts');
  return response.data;
};

export const postSaveLayout = async (payload: LayoutSavePayload) => {
  const response = await apiClient.post('/api/layouts', payload);
  return response.data;
};

export const fetchLayoutSnapshot = async () => {
  const response = await apiClient.get('/api/layout');
  return response.data;
};

export const postRestoreLayout = async (payload: LayoutSlotActionPayload) => {
  const response = await apiClient.post('/api/layouts/restore', payload);
  return response.data;
};

export const postDeleteLayout = async (payload: LayoutSlotActionPayload) => {
  const response = await apiClient.post('/api/layouts/delete', payload);
  return response.data;
};

export const fetchClientLatestLayout = async (clientId: string): Promise<LayoutSnapshot> => {
  const response = await apiClient.get<LayoutSnapshot>(`/api/layouts/client/${clientId}/latest`);
  return response.data;
};

export const fetchClientLayoutList = async (clientId: string): Promise<ClientLayoutListItem[]> => {
  const response = await apiClient.get<ClientLayoutListItem[]>(`/api/layouts/client/${clientId}/list`);
  return response.data;
};

export const fetchClientLayoutSlot = async (
  clientId: string,
  slotId: string
): Promise<LayoutSnapshot> => {
  const response = await apiClient.get<LayoutSnapshot>(`/api/layouts/client/${clientId}/${slotId}`);
  return response.data;
};

export const postClientLayout = async (clientId: string, payload: ClientLayoutSavePayload) =>
  apiClient.post(`/api/layouts/client/${clientId}`, payload);

export const deleteClientLayoutSlot = async (clientId: string, slotId: string) =>
  apiClient.delete(`/api/layouts/client/${clientId}/${slotId}`);
