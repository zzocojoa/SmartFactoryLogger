import { EXPORT_PATH_STORAGE_KEY } from '../../../shared/constants/logic';
import { safeGetItem, safeSetItem, safeRemoveItem } from '../../../shared/utils/safeStorage';

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
