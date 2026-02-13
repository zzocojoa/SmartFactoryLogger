import type { SpotConfig } from '../types';

export interface UseSpotViewModel {
  config: SpotConfig | null;
  imageUrl: string;
  imageError: string | null;
  imageLoading: boolean;
  lastSuccessAt: number | null;
  focusBusy: boolean;
  refreshConfig: () => Promise<void>;
  refreshImage: () => void;
  controlSpot: (action: string, value?: number) => Promise<boolean>;
  controlFocus: (steps: number) => Promise<void>;
  controlActuator: (step: number) => Promise<void>;
  handleImageLoad: () => void;
  handleImageError: () => void;
}
