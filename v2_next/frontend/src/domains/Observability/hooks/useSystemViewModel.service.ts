import { EXPORT_PATH_STORAGE_KEY } from '../../../shared/constants/logic';
import { safeGetItem, safeSetItem, safeRemoveItem } from '../../../shared/utils/safeStorage';

const COMM_LOG_PATH_STORAGE_KEY = 'smartfactory_comm_log_path_v1';

export const readPersistedExportPath = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  return safeGetItem(EXPORT_PATH_STORAGE_KEY);
};

export const persistExportPath = (path: string | null): void => {
  if (typeof window === 'undefined') {
    return;
  }
  if (path) {
    safeSetItem(EXPORT_PATH_STORAGE_KEY, path);
    return;
  }
  safeRemoveItem(EXPORT_PATH_STORAGE_KEY);
};

export const readPersistedCommLogPath = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  return safeGetItem(COMM_LOG_PATH_STORAGE_KEY);
};

export const persistCommLogPath = (path: string | null): void => {
  if (typeof window === 'undefined') {
    return;
  }
  if (path) {
    safeSetItem(COMM_LOG_PATH_STORAGE_KEY, path);
    return;
  }
  safeRemoveItem(COMM_LOG_PATH_STORAGE_KEY);
};
