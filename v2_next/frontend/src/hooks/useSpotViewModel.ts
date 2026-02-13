import { useState, useCallback, useRef } from 'react';
import type { SpotConfig } from '../types';
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
} from './useSpotViewModel.selectors';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';
import type { UseSpotViewModel } from './useSpotViewModel.types';

export const useSpotViewModel = (): UseSpotViewModel => {
  const [config, setConfig] = useState<SpotConfig | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);

  const hasImageRef = useRef(false);
  const prevUrlRef = useRef<string | null>(null);
  const inFlightRef = useRef(false);

  const refreshConfig = useCallback(async () => {
    try {
      const data = await fetchSpotConfig();
      setConfig(data);
    } catch (error) {
      console.error('Failed to load spot config', error);
    }
  }, []);

  const fetchImage = useCallback(async () => {
    if (!config?.image_url) return;
    if (inFlightRef.current) return;
    inFlightRef.current = true;

    if (!hasImageRef.current) setImageLoading(true);

    try {
      const response = await fetchSpotImageResponse();
      if (!response.ok) throw new Error('Network response was not ok');

      const statusHeader = response.headers.get('X-Spot-Image-Status');
      const capturedAtHeader = response.headers.get('X-Spot-Image-At');
      const ageHeader = response.headers.get('X-Spot-Image-Age');
      const blob = await response.blob();

      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
      }

      const newUrl = URL.createObjectURL(blob);
      prevUrlRef.current = newUrl;
      setImageUrl(newUrl);
      setImageError(null);
      hasImageRef.current = true;

      const receivedAt = Date.now();
      const effectiveAt = resolveEffectiveSpotImageAt(capturedAtHeader, ageHeader, receivedAt);
      setLastSuccessAt(effectiveAt);

      if (statusHeader === 'stale') {
        setImageError(null);
      }
    } catch (err) {
      console.error('Image fetch failed', err);
      setImageError(resolveSpotImageErrorMessage());
    } finally {
      setImageLoading(false);
      inFlightRef.current = false;
    }
  }, [config]);

  const refreshImage = useCallback(() => {
    void fetchImage();
  }, [fetchImage]);

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
      if (focusBusy) return;
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

  useSpotViewModelEffects({ config, fetchImage, refreshConfig, prevUrlRef });

  const handleImageLoad = useCallback(() => {
    hasImageRef.current = true;
    setImageLoading(false);
  }, []);

  const handleImageError = useCallback(() => {
    setImageLoading(false);
    if (!imageError) setImageError(resolveSpotImageLoadErrorMessage());
  }, [imageError]);

  return {
    config,
    imageUrl,
    imageError,
    imageLoading,
    lastSuccessAt,
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
