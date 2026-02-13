import { EXPORT_PATH_STORAGE_KEY } from '../constants/logic';

export const readPersistedExportPath = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem(EXPORT_PATH_STORAGE_KEY);
};

export const persistExportPath = (path: string | null): void => {
  if (typeof window === 'undefined') {
    return;
  }
  if (path) {
    window.localStorage.setItem(EXPORT_PATH_STORAGE_KEY, path);
    return;
  }
  window.localStorage.removeItem(EXPORT_PATH_STORAGE_KEY);
};
