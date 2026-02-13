import { useEffect } from 'react';
import type { MutableRefObject } from 'react';
import type { SpotConfig } from '../types';
import { resolveSpotRefreshMs } from './useSpotViewModel.selectors';

interface UseSpotViewModelEffectsParams {
  config: SpotConfig | null;
  fetchImage: () => Promise<void>;
  refreshConfig: () => Promise<void>;
  prevUrlRef: MutableRefObject<string | null>;
}

export const useSpotViewModelEffects = ({
  config,
  fetchImage,
  refreshConfig,
  prevUrlRef,
}: UseSpotViewModelEffectsParams) => {
  useEffect(() => {
    if (!config || !config.image_url) {
      return;
    }

    let active = true;
    let timerId: ReturnType<typeof setTimeout> | null = null;

    const loop = async () => {
      if (!active) {
        return;
      }

      const refreshMs = resolveSpotRefreshMs(config.refresh_interval);
      const hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden';
      if (!hidden) {
        await fetchImage();
      }

      if (active) {
        timerId = setTimeout(loop, refreshMs);
      }
    };

    loop();

    return () => {
      active = false;
      if (timerId) {
        clearTimeout(timerId);
      }
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = null;
      }
    };
  }, [config, fetchImage, prevUrlRef]);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        void fetchImage();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [fetchImage]);

  useEffect(() => {
    void refreshConfig();
  }, [refreshConfig]);
};
