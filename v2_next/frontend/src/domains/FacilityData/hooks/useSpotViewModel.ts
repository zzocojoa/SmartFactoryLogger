import { useCallback, useRef, useState } from 'react';
import type { SpotConfig, SpotPollingDiagnostics } from '../../../shared/types';
import { useDashboardStore } from '../../../store/useDashboardStore';
import {
  controlSpotAction,
  controlSpotActuator,
  controlSpotFocus,
  fetchSpotConfig,
  fetchSpotImageResponse,
} from './useSpotViewModel.service';
import {
  resolveEffectiveSpotImageAt,
  resolveSpotImageErrorMessage,
  resolveSpotImageLoadErrorMessage,
  resolveSpotRefreshMs,
} from './useSpotViewModel.selectors';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';
import type { UseSpotViewModel } from './useSpotViewModel.types';

interface SpotImageState {
  imageUrl: string;
  imageError: string | null;
  lastSuccessAt: number | null;
}

const INITIAL_SPOT_DIAGNOSTICS: SpotPollingDiagnostics = {
  in_flight: false,
  refresh_interval_ms: null,
  fetch_count: 0,
  error_count: 0,
  last_fetch_started_at: null,
  last_fetch_completed_at: null,
  last_fetch_latency_ms: null,
  next_fetch_scheduled_at: null,
  last_fetch_reason: null,
};

export const useSpotViewModel = (): UseSpotViewModel => {
  const [config, setConfig] = useState<SpotConfig | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);
  const [diagnostics, setDiagnostics] = useState<SpotPollingDiagnostics>(INITIAL_SPOT_DIAGNOSTICS);

  const hasImageRef = useRef(false);
  const prevUrlRef = useRef<string | null>(null);
  const inFlightRef = useRef(false);
  const configRef = useRef<SpotConfig | null>(null);
  const nextFetchScheduledAtRef = useRef<number | null>(null);
  const imageStateRef = useRef<SpotImageState>({
    imageUrl: '',
    imageError: null,
    lastSuccessAt: null,
  });

  const setDashboardSpotConfig = useDashboardStore((state) => state.setSpotConfig);
  const setDashboardSpotImageState = useDashboardStore((state) => state.setSpotImageState);

  configRef.current = config;

  const syncDashboardSpotImageState = useCallback(
    (nextImageUrl: string, nextLoading: boolean, nextImageError: string | null, nextLastSuccessAt: number | null) => {
      setDashboardSpotImageState(nextImageUrl, nextLoading, nextImageError, nextLastSuccessAt);
    },
    [setDashboardSpotImageState]
  );

  const refreshConfig = useCallback(async () => {
    try {
      const data = await fetchSpotConfig();
      setConfig(data);
      setDashboardSpotConfig(data);
      setDiagnostics((prev) => ({
        ...prev,
        refresh_interval_ms: resolveSpotRefreshMs(data.refresh_interval),
      }));
    } catch (error) {
      console.error('Failed to load spot config', error);
    }
  }, [setDashboardSpotConfig]);

  const setNextFetchScheduledAt = useCallback((nextFetchScheduledAt: number | null) => {
    nextFetchScheduledAtRef.current = nextFetchScheduledAt;
    setDiagnostics((prev) => ({
      ...prev,
      next_fetch_scheduled_at: nextFetchScheduledAt,
      refresh_interval_ms: configRef.current
        ? resolveSpotRefreshMs(configRef.current.refresh_interval)
        : null,
    }));
  }, []);

  const shouldFetchOnVisibility = useCallback((): boolean => {
    if (inFlightRef.current) {
      return false;
    }
    const nextFetchScheduledAt = nextFetchScheduledAtRef.current;
    if (nextFetchScheduledAt === null) {
      return true;
    }
    return nextFetchScheduledAt - Date.now() > 250;
  }, []);

  const runSpotFetch = useCallback(
    async (reason: string): Promise<void> => {
      const currentConfig = configRef.current;
      if (!currentConfig?.image_url) {
        return;
      }
      if (inFlightRef.current) {
        return;
      }

      const refreshIntervalMs = resolveSpotRefreshMs(currentConfig.refresh_interval);
      const startedAt = Date.now();
      const currentImageState = imageStateRef.current;

      inFlightRef.current = true;
      setDiagnostics((prev) => ({
        ...prev,
        in_flight: true,
        refresh_interval_ms: refreshIntervalMs,
        fetch_count: prev.fetch_count + 1,
        last_fetch_started_at: startedAt,
        last_fetch_reason: reason,
      }));

      if (!hasImageRef.current) {
        setImageLoading(true);
        syncDashboardSpotImageState(
          currentImageState.imageUrl,
          true,
          currentImageState.imageError,
          currentImageState.lastSuccessAt
        );
      }

      try {
        const response = await fetchSpotImageResponse();
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }

        const capturedAtHeader = response.headers.get('X-Spot-Image-At');
        const ageHeader = response.headers.get('X-Spot-Image-Age');
        const blob = await response.blob();

        if (prevUrlRef.current) {
          URL.revokeObjectURL(prevUrlRef.current);
        }

        const receivedAt = Date.now();
        const effectiveAt = resolveEffectiveSpotImageAt(capturedAtHeader, ageHeader, receivedAt);
        const nextImageUrl = URL.createObjectURL(blob);

        prevUrlRef.current = nextImageUrl;
        imageStateRef.current = {
          imageUrl: nextImageUrl,
          imageError: null,
          lastSuccessAt: effectiveAt,
        };
        hasImageRef.current = true;

        setImageUrl(nextImageUrl);
        setImageError(null);
        setLastSuccessAt(effectiveAt);
        syncDashboardSpotImageState(nextImageUrl, false, null, effectiveAt);
      } catch (error) {
        console.error('Image fetch failed', error);
        const nextImageError = resolveSpotImageErrorMessage();
        const nextImageState = {
          ...imageStateRef.current,
          imageError: nextImageError,
        };
        imageStateRef.current = nextImageState;
        setImageError(nextImageError);
        syncDashboardSpotImageState(
          nextImageState.imageUrl,
          false,
          nextImageError,
          nextImageState.lastSuccessAt
        );
        setDiagnostics((prev) => ({
          ...prev,
          error_count: prev.error_count + 1,
        }));
      } finally {
        const completedAt = Date.now();
        setImageLoading(false);
        inFlightRef.current = false;
        setDiagnostics((prev) => ({
          ...prev,
          in_flight: false,
          last_fetch_completed_at: completedAt,
          last_fetch_latency_ms: completedAt - startedAt,
        }));
      }
    },
    [syncDashboardSpotImageState]
  );

  const fetchScheduledImage = useCallback(async (): Promise<void> => {
    await runSpotFetch('scheduled');
  }, [runSpotFetch]);

  const fetchVisibleImage = useCallback(async (): Promise<void> => {
    await runSpotFetch('visible');
  }, [runSpotFetch]);

  const refreshImage = useCallback(() => {
    void runSpotFetch('manual');
  }, [runSpotFetch]);

  const controlSpot = useCallback(async (action: string, value?: number) => {
    try {
      await controlSpotAction(action, value);
      return true;
    } catch (error) {
      console.error('Spot control failed', error);
      return false;
    }
  }, []);

  const controlFocus = useCallback(
    async (steps: number) => {
      if (focusBusy) {
        return;
      }
      setFocusBusy(true);
      try {
        await controlSpotFocus(steps);
      } catch (error) {
        console.error('Spot focus failed', error);
      } finally {
        setFocusBusy(false);
      }
    },
    [focusBusy]
  );

  const controlActuator = useCallback(async (step: number) => {
    try {
      await controlSpotActuator(step);
    } catch (error) {
      console.error('Spot actuator failed', error);
    }
  }, []);

  useSpotViewModelEffects({
    config,
    fetchScheduledImage,
    fetchVisibleImage,
    refreshConfig,
    prevUrlRef,
    setNextFetchScheduledAt,
    shouldFetchOnVisibility,
  });

  const handleImageLoad = useCallback(() => {
    hasImageRef.current = true;
    setImageLoading(false);
    const currentImageState = imageStateRef.current;
    syncDashboardSpotImageState(
      currentImageState.imageUrl,
      false,
      currentImageState.imageError,
      currentImageState.lastSuccessAt
    );
  }, [syncDashboardSpotImageState]);

  const handleImageError = useCallback(() => {
    setImageLoading(false);
    const currentImageState = imageStateRef.current;
    if (!currentImageState.imageError) {
      const nextImageError = resolveSpotImageLoadErrorMessage();
      imageStateRef.current = {
        ...currentImageState,
        imageError: nextImageError,
      };
      setImageError(nextImageError);
      syncDashboardSpotImageState(
        currentImageState.imageUrl,
        false,
        nextImageError,
        currentImageState.lastSuccessAt
      );
      return;
    }
    syncDashboardSpotImageState(
      currentImageState.imageUrl,
      false,
      currentImageState.imageError,
      currentImageState.lastSuccessAt
    );
  }, [syncDashboardSpotImageState]);

  return {
    config,
    imageUrl,
    imageError,
    imageLoading,
    lastSuccessAt,
    diagnostics,
    focusBusy,
    refreshConfig,
    refreshImage,
    handleImageLoad,
    handleImageError,
    controlSpot,
    controlFocus,
    controlActuator,
  };
};
