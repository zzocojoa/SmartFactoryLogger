import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export type ThemeMode = 'auto' | 'light' | 'dark';
export type ThemeCycle = 'day' | 'sunset' | 'night';

interface ThemeState {
  mode: ThemeMode;
  activeCycle: ThemeCycle;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    return (localStorage.getItem('theme_mode') as ThemeMode) || 'auto';
  });

  const [activeCycle, setActiveCycle] = useState<ThemeCycle>('day');

  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    localStorage.setItem('theme_mode', newMode);
  }, []);

  const calculateCycle = useCallback((): ThemeCycle => {
    const hour = new Date().getHours();
    // Day: 08:00 - 18:00
    if (hour >= 8 && hour < 18) return 'day';
    // Sunset: 18:00 - 20:00
    if (hour >= 18 && hour < 20) return 'sunset';
    // Night: 20:00 - 08:00 (else)
    return 'night';
  }, []);

  useEffect(() => {
    const updateTheme = () => {
      let targetCycle: ThemeCycle = 'day';

      if (mode === 'auto') {
        targetCycle = calculateCycle();
      } else if (mode === 'light') {
        targetCycle = 'day';
      } else if (mode === 'dark') {
        targetCycle = 'night';
      }

      setActiveCycle(targetCycle);
      document.body.setAttribute('data-theme', targetCycle);
    };

    updateTheme(); // Initial call

    // Check every minute
    const interval = setInterval(updateTheme, 60 * 1000);
    return () => clearInterval(interval);
  }, [mode, calculateCycle]);

  return (
    <ThemeContext.Provider value={{ mode, activeCycle, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
};
