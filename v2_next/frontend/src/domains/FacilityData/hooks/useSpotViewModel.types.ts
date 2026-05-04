import type { SpotConfig, SpotPollingDiagnostics } from '../../../shared/types';
import type { SpotImageResponseMetadata } from '../api/spotService.types';

export interface UseSpotViewModel {
  config: SpotConfig | null;
  imageUrl: string;
  imageError: string | null;
  imageLoading: boolean;
  lastSuccessAt: number | null;
  metadata: SpotImageResponseMetadata | null;
  diagnostics: SpotPollingDiagnostics;
  focusBusy: boolean;
  refreshConfig: () => Promise<void>;
  refreshImage: () => void;
  controlSpot: (action: string, value?: number) => Promise<boolean>;
  controlFocus: (steps: number) => Promise<void>;
  controlActuator: (step: number) => Promise<void>;
  handleImageLoad: () => void;
  handleImageError: () => void;
}
