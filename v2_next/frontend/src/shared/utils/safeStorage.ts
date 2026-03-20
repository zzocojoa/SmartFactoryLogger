/**
 * Safe local storage wrapper.
 * Provides safe fallback mechanisms if localStorage is disabled or throws errors.
 */

export const safeGetItem = (key: string, defaultValue: string | null = null): string | null => {
  if (typeof window === 'undefined') return defaultValue;
  try {
    const value = window.localStorage.getItem(key);
    return value !== null ? value : defaultValue;
  } catch (error) {
    console.warn(`[SafeStorage] Failed to read key: ${key}`, error);
    return defaultValue;
  }
};

export const safeSetItem = (key: string, value: string): void => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn(`[SafeStorage] Failed to set key: ${key}`, error);
  }
};

export const safeRemoveItem = (key: string): void => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    console.warn(`[SafeStorage] Failed to remove key: ${key}`, error);
  }
};
