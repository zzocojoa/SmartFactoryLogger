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
  const prevUrlRef = useRef<string | null>(null);
  const inFlightRef = useRef(false);

  const refreshConfig = useCallback(async () => {
    try {
      const data = await spotService.getConfig();
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
          // Use fetch instead of img src for memory control
          const url = `${spotService.getImageUrl()}?t=${Date.now()}`;
          const response = await fetch(url, { cache: 'no-store' });
          
          if (!response.ok) throw new Error('Network response was not ok');

          const statusHeader = response.headers.get('X-Spot-Image-Status');
          const capturedAtHeader = response.headers.get('X-Spot-Image-At');
          const ageHeader = response.headers.get('X-Spot-Image-Age');
          
          const blob = await response.blob();
          
          // Revoke previous URL to prevent memory leaks
          if (prevUrlRef.current) {
              URL.revokeObjectURL(prevUrlRef.current);
          }
          
          const newUrl = URL.createObjectURL(blob);
          prevUrlRef.current = newUrl;
          setImageUrl(newUrl);
          setImageError(null);
          hasImageRef.current = true;

          const receivedAt = Date.now();
          let effectiveAt = receivedAt;
          const capturedAt = capturedAtHeader ? Number(capturedAtHeader) : NaN;
          const ageSec = ageHeader ? Number(ageHeader) : NaN;
          
          // Fix: Prefer relative age (ageSec) to avoid server-client clock skew
          if (Number.isFinite(ageSec)) {
              effectiveAt = receivedAt - Math.max(0, ageSec * 1000);
          } else if (Number.isFinite(capturedAt)) {
              effectiveAt = capturedAt;
          }
          setLastSuccessAt(effectiveAt);
          if (statusHeader === 'stale') {
              setImageError(null);
          }
          
      } catch (err) {
          console.error('Image fetch failed', err);
          setImageError('이미지 수신 실패');
      } finally {
          setImageLoading(false);
          inFlightRef.current = false;
      }
  }, [config]);

  const refreshImage = useCallback(() => {
    fetchImage();
  }, [fetchImage]);

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

  // Smart Polling
  useEffect(() => {
    if (!config || !config.image_url) return;
    
    let active = true;
    let timerId: NodeJS.Timeout;
    
    const loop = async () => {
       if (!active) return;

       const refreshMs = Math.max(500, Math.round(config.refresh_interval * 1000));
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
        if (timerId) clearTimeout(timerId);
        // Cleanup final Blob URL
        if (prevUrlRef.current) {
            URL.revokeObjectURL(prevUrlRef.current);
            prevUrlRef.current = null;
        }
    };
  }, [config, fetchImage]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchImage();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [fetchImage]);

  // Initial config load
  useEffect(() => {
    refreshConfig();
  }, [refreshConfig]);

  const handleImageLoad = useCallback(() => {
    // Legacy handler: The loading state is now managed by fetchImage
    hasImageRef.current = true;
    setImageLoading(false); 
  }, []);

  const handleImageError = useCallback(() => {
    // Legacy handler
    setImageLoading(false);
    if (!imageError) setImageError('이미지 로드 실패');
  }, [imageError]);

  return {
    config,
    imageUrl,
    imageError,
    imageLoading,
    lastSuccessAt,
    focusBusy,
    
    refreshConfig,
    refreshImage, // Manual refresh
    handleImageLoad,
    handleImageError,
    controlSpot,
    controlFocus,
    controlActuator
  };
};
