import type { ThemeCycle, ThemeMode } from '../types/ThemeContext.types';

const THEME_STORAGE_KEY = 'theme_mode';

export const readThemeMode = (): ThemeMode => {
  const stored = localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
  return stored ?? 'auto';
};

export const persistThemeMode = (mode: ThemeMode): void => {
  localStorage.setItem(THEME_STORAGE_KEY, mode);
};

export const calculateThemeCycle = (hour: number): ThemeCycle => {
  if (hour >= 8 && hour < 18) {
    return 'day';
  }
  if (hour >= 18 && hour < 20) {
    return 'sunset';
  }
  return 'night';
};

export const resolveThemeCycle = (mode: ThemeMode, hour: number): ThemeCycle => {
  if (mode === 'auto') {
    return calculateThemeCycle(hour);
  }
  if (mode === 'light') {
    return 'day';
  }
  return 'night';
};

export const applyThemeCycle = (cycle: ThemeCycle): void => {
  document.body.setAttribute('data-theme', cycle);
};
