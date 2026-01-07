import { useState, useCallback, useRef, useEffect } from 'react';
import { spotService } from '../api/spotService';
import { SpotConfig } from '../types';

export interface UseSpotViewModel {
  config: SpotConfig | null;
  imageUrl: string;
  imageError: string | null;
  imageLoading: boolean;
  lastSuccessAt: number | null;
  focusBusy: boolean;

  // Actions
  refreshConfig: () => Promise<void>;
  refreshImage: () => void;
  controlSpot: (action: string, value?: number) => Promise<boolean>;
  controlFocus: (steps: number) => Promise<void>;
  controlActuator: (step: number) => Promise<void>;
  handleImageLoad: () => void;
  handleImageError: () => void;
}

export const useSpotViewModel = (): UseSpotViewModel => {
  const [config, setConfig] = useState<SpotConfig | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);
  
  const hasImageRef = useRef(false);

  const refreshConfig = useCallback(async () => {
    try {
      const data = await spotService.getConfig();
      setConfig(data);
    } catch (error) {
       console.error('Failed to load spot config', error);
    }
  }, []);

  const refreshImage = useCallback(() => {
    setImageLoading(true);
    // Add timestamp to prevent caching
    const url = `${spotService.getImageUrl()}?t=${Date.now()}`;
    setImageUrl(url);
    // Note: The actual loading state is usually cleared by the <img> onLoad handler 
    // in the View, but we can manage specific logic here if needed.
    // For now, we set the URL. The error state is reset when a new URL is set.
    setImageError(null);
  }, []);

  const controlSpot = useCallback(async (action: string, value?: number) => {
    try {
        await spotService.control({ action, value });
        return true;
    } catch (error) {
        console.error('Spot control failed', error);
        return false;
    }
  }, []);

  const controlFocus = useCallback(async (steps: number) => {
      if (focusBusy) return;
      setFocusBusy(true);
      try {
          await spotService.focus(steps);
      } catch (error) {
          console.error('Spot focus failed', error);
      } finally {
          setFocusBusy(false);
      }
  }, [focusBusy]);

  const controlActuator = useCallback(async (step: number) => {
      try {
          await spotService.actuator(step);
      } catch (error) {
          console.error('Spot actuator failed', error);
      }
  }, []);
  // Polling for image
  useEffect(() => {
    if (!config || !config.image_url) return;
    const refreshMs = Math.max(500, Math.round(config.refresh_interval * 1000));
    
    // We use a ref to track if we show loading state
    // In strict mode, we might want to be careful, but this matches App.tsx
    const updateImage = () => {
       if (!hasImageRef.current) setImageLoading(true);
       // Use proxy_image as per App.tsx
       // We need API_BASE? spotService.getImageUrl() should return the full path or client handles it.
       // actually App.tsx uses `${API_BASE}/api/spot/proxy_image`
       // But spotService uses apiClient which has baseURL.
       // For <img> src, we need the full URL including protocol/host if it's on a different port,
       // OR just the relative path if we are proxying correctly.
       // Assuming relative path works if served from same origin, or use helper.
       // Let's assume spotService.getImageUrl() provides the base path.
       // We'll update spotService to be consistent or just use the string here.
       
       // App.tsx uses: `${API_BASE}/api/spot/proxy_image?t=${Date.now()}`
       // spotService.getImageUrl() now returns the full path with API_BASE
       const baseUrl = spotService.getImageUrl();
       setImageUrl(`${baseUrl}?t=${Date.now()}`);
    };

    updateImage();
    const timer = setInterval(updateImage, refreshMs);
    return () => clearInterval(timer);
  }, [config]);

  // Initial config load
  useEffect(() => {
    refreshConfig();
  }, [refreshConfig]);

  const handleImageLoad = useCallback(() => {
    hasImageRef.current = true;
    setImageLoading(false);
    setImageError(null);
    setLastSuccessAt(Date.now());
  }, []);

  const handleImageError = useCallback(() => {
    setImageLoading(false);
    setImageError('이미지 수신 실패');
  }, []);

  return {
    config,
    imageUrl,
    imageError,
    imageLoading,
    lastSuccessAt,
    focusBusy,
    
    refreshConfig,
    refreshImage, // Manual refresh if needed
    handleImageLoad,
    handleImageError,
    controlSpot,
    controlFocus,
    controlActuator
  };
};
