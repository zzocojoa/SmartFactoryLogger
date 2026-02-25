import type {
  ConfigPayload,
  GenericApiResponse,
  OverridePayload,
  PasswordVerificationResponse,
} from './configService.types';
import {
  fetchCentralStatus,
  fetchConfig,
  fetchNotice,
  postApplyPending,
  postCentralSync,
  postClearPending,
  postConfig,
  postConnectionTest,
  postNotice,
  postRestoreBackup,
  postRestoreDefaults,
  postToggleOverride,
  postVerifyPassword,
} from '../../../shared/api/transport/configService.transport';

export const configService = {
  getConfig: fetchConfig,

  saveConfig: (config: ConfigPayload) => postConfig(config),

  getNotice: fetchNotice,

  saveNotice: (content: string) => postNotice(content),

  testConnection: (target: string, params: GenericApiResponse) => postConnectionTest(target, params),

  getCentralStatus: fetchCentralStatus,

  syncCentral: postCentralSync,

  restoreDefaults: postRestoreDefaults,

  restoreBackup: postRestoreBackup,

  applyPending: postApplyPending,

  clearPending: postClearPending,

  toggleOverride: (params: OverridePayload) => postToggleOverride(params),

  verifyPassword: (password: string): Promise<PasswordVerificationResponse> =>
    postVerifyPassword(password),
};
