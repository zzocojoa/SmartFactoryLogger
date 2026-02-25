import React, { createContext, useState, useEffect, useCallback } from 'react';
import {
  applyThemeCycle,
  persistThemeMode,
  readThemeMode,
  resolveThemeCycle,
} from '../services/ThemeContext.service';
import type { ThemeMode, ThemeState } from '../types/ThemeContext.types';

export type { ThemeMode, ThemeCycle, ThemeState } from '../types/ThemeContext.types';

export const ThemeContext = createContext<ThemeState | null>(null);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setModeState] = useState<ThemeMode>(readThemeMode);

  const [activeCycle, setActiveCycle] = useState<ThemeState['activeCycle']>('day');

  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    persistThemeMode(newMode);
  }, []);

  useEffect(() => {
    const updateTheme = () => {
      const targetCycle = resolveThemeCycle(mode, new Date().getHours());
      setActiveCycle(targetCycle);
      applyThemeCycle(targetCycle);
    };

    updateTheme();

    const interval = setInterval(updateTheme, 60 * 1000);
    return () => clearInterval(interval);
  }, [mode]);

  return (
    <ThemeContext.Provider value={{ mode, activeCycle, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
};
