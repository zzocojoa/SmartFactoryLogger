/**
 * SpotContext: Spot 카메라 설정 및 이미지 상태를 관리하는 Context
 */
import React from 'react';
import type { SpotConfig } from '../../../shared/types';

export type SpotContextValue = {
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotAlertActive: boolean;
  onSpotImageLoaded: () => void;
  onSpotImageError: (message?: string) => void;
  requestFocus: (steps: number) => void;
};

export const SpotContext = React.createContext<SpotContextValue>({
  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotAlertActive: false,
  onSpotImageLoaded: () => undefined,
  onSpotImageError: () => undefined,
  requestFocus: () => undefined,
});
