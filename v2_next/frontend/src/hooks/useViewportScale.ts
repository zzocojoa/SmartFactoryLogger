import { useState, useEffect, useCallback } from 'react';
import {
  DEFAULT_ROW_HEIGHT,
  MIN_ROW_HEIGHT,
  MAX_ROW_HEIGHT,
  BASE_VIEWPORT_HEIGHT
} from '../constants/logic';

export interface ViewportScaleResult {
  rowHeight: number;
  scaleFactor: number;
  viewportHeight: number;
  viewportWidth: number;
  aspectRatio: string;
}

/**
 * Hook to calculate dynamic row height based on viewport size.
 * Base: 1080p (1920x1080) → 20px row height
 * Scales proportionally with viewport height, clamped to min/max.
 */
export function useViewportScale(): ViewportScaleResult {
  const calculateScale = useCallback(() => {
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    
    // Calculate scale factor based on viewport height
    const scaleFactor = vh / BASE_VIEWPORT_HEIGHT;
    
    // Calculate row height with clamping
    const rawRowHeight = DEFAULT_ROW_HEIGHT * scaleFactor;
    const rowHeight = Math.max(MIN_ROW_HEIGHT, Math.min(MAX_ROW_HEIGHT, Math.round(rawRowHeight)));
    
    // Detect aspect ratio
    const ratio = vw / vh;
    let aspectRatio: string;
    if (ratio >= 2.2) {
      aspectRatio = '21:9';
    } else if (ratio >= 1.6) {
      aspectRatio = '16:9';
    } else if (ratio >= 1.2) {
      aspectRatio = '4:3';
    } else {
      aspectRatio = 'portrait';
    }
    
    return {
      rowHeight,
      scaleFactor,
      viewportHeight: vh,
      viewportWidth: vw,
      aspectRatio
    };
  }, []);

  const [scale, setScale] = useState<ViewportScaleResult>(calculateScale);

  useEffect(() => {
    const handleResize = () => {
      setScale(calculateScale());
    };

    // Listen for resize events
    window.addEventListener('resize', handleResize);
    
    // Initial calculation
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [calculateScale]);

  return scale;
}

/**
 * Apply row height to CSS variable for Grafana Scenes grid override.
 */
export function applyRowHeightToCSS(rowHeight: number): void {
  document.documentElement.style.setProperty('--grid-row-height', `${rowHeight}px`);
}
