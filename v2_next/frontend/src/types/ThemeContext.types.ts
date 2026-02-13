export type ThemeMode = 'auto' | 'light' | 'dark';
export type ThemeCycle = 'day' | 'sunset' | 'night';

export interface ThemeState {
  mode: ThemeMode;
  activeCycle: ThemeCycle;
  setMode: (mode: ThemeMode) => void;
}
