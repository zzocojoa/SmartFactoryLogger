import { useEffect } from 'react';
import type { MutableRefObject } from 'react';
import type { SpotConfig } from '../../../shared/types';
import { resolveSpotRefreshMs } from './useSpotViewModel.selectors';

interface UseSpotViewModelEffectsParams {
  config: SpotConfig | null;
  fetchScheduledImage: () => Promise<void>;
  fetchVisibleImage: () => Promise<void>;
  refreshConfig: () => Promise<void>;
  prevUrlRef: MutableRefObject<string | null>;
  setNextFetchScheduledAt: (nextFetchScheduledAt: number | null) => void;
  shouldFetchOnVisibility: () => boolean;
}

export const useSpotViewModelEffects = ({
  config,
  fetchScheduledImage,
  fetchVisibleImage,
  refreshConfig,
  prevUrlRef,
  setNextFetchScheduledAt,
  shouldFetchOnVisibility,
}: UseSpotViewModelEffectsParams) => {
  useEffect(() => {
    if (!config || !config.image_url) {
      setNextFetchScheduledAt(null);
      return;
    }

    let active = true;
    let timerId: ReturnType<typeof setTimeout> | null = null;
    const refreshMs = resolveSpotRefreshMs(config.refresh_interval);

    const scheduleNext = (targetAt: number) => {
      if (!active) {
        return;
      }
      setNextFetchScheduledAt(targetAt);
      timerId = setTimeout(loop, Math.max(0, targetAt - Date.now()));
    };

    const loop = async () => {
      if (!active) {
        return;
      }

      const startedAt = Date.now();
      const hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden';
      if (!hidden) {
        await fetchScheduledImage();
      }

      if (active) {
        scheduleNext(startedAt + refreshMs);
      }
    };

    void loop();

    return () => {
      active = false;
      if (timerId) {
        clearTimeout(timerId);
      }
      setNextFetchScheduledAt(null);
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = null;
      }
    };
  }, [
    config?.image_url,
    config?.refresh_interval,
    fetchScheduledImage,
    prevUrlRef,
    setNextFetchScheduledAt,
  ]);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && shouldFetchOnVisibility()) {
        void fetchVisibleImage();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [fetchVisibleImage, shouldFetchOnVisibility]);

  useEffect(() => {
    void refreshConfig();
  }, [refreshConfig]);
};
