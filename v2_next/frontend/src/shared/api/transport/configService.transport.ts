import { apiClient } from '../client';
import type {
  ConfigPayload,
  GenericApiResponse,
  OverridePayload,
  PasswordVerificationResponse,
} from '../../../domains/Configuration/api/configService.types';

export const fetchConfig = async () => {
  const response = await apiClient.get('/api/config');
  return response.data;
};

export const postConfig = async (config: ConfigPayload) => {
  const response = await apiClient.post('/api/config', config);
  return response.data;
};

export const fetchNotice = async () => {
  const response = await apiClient.get('/api/config/notice');
  return response.data;
};

export const postNotice = async (content: string) => {
  const response = await apiClient.post('/api/config/notice', { content });
  return response.data;
};

export const postConnectionTest = async (target: string, params: GenericApiResponse) => {
  const response = await apiClient.post(`/api/config/test/${target}`, params);
  return response.data;
};

export const fetchCentralStatus = async () => {
  const response = await apiClient.get('/api/config/central-status');
  return response.data;
};

export const postCentralSync = async () => {
  const response = await apiClient.post('/api/config/sync');
  return response.data;
};

export const postRestoreDefaults = async () => apiClient.post('/api/config/restore-defaults');

export const postRestoreBackup = async () => apiClient.post('/api/config/restore-backup');

export const postApplyPending = async () => apiClient.post('/api/config/pending/apply');

export const postClearPending = async () => apiClient.post('/api/config/pending/clear');

export const postToggleOverride = async (params: OverridePayload) => {
  const response = await apiClient.post('/api/config/override', params);
  return response.data;
};

export const postVerifyPassword = async (
  password: string
): Promise<PasswordVerificationResponse> => {
  const response = await apiClient.post<PasswordVerificationResponse>('/api/config/verify-password', {
    password,
  });
  return response.data;
};
