/**
 * UIContext: 대시보드 UI 상태(윈도우 크기, 일시정지, 레이아웃 보이기 등)를 관리하는 Context
 */
import React from 'react';

export type UIContextValue = {
  seriesWindowMin: number;
  seriesPaused: boolean;
  showThresholds: boolean;
  layoutEditing: boolean;
  setSeriesWindowMin: (min: number) => void;
  setSeriesPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setShowThresholds: (show: boolean) => void;
  setLayoutEditing: (editing: boolean) => void;
};

export const UIContext = React.createContext<UIContextValue>({
  seriesWindowMin: 30,
  seriesPaused: false,
  showThresholds: true,
  layoutEditing: false,
  setSeriesWindowMin: () => undefined,
  setSeriesPaused: () => undefined,
  setShowThresholds: () => undefined,
  setLayoutEditing: () => undefined,
});
