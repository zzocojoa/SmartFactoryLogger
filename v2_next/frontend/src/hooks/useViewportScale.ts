import { useState, useCallback } from 'react';
import {
  DEFAULT_ROW_HEIGHT,
  MIN_ROW_HEIGHT,
  MAX_ROW_HEIGHT,
  BASE_VIEWPORT_HEIGHT
} from '../constants/logic';
import { resolveAspectRatioLabel, resolveRowHeight } from './useViewportScale.selectors';
import { useViewportScaleEffects } from './useViewportScaleEffects';
import type { ViewportScaleResult } from './useViewportScale.types';
export { applyRowHeightToCSS } from './useViewportScale.service';

/**
 * Hook to calculate dynamic row height based on viewport size.
 * Base: 1080p (1920x1080) → 20px row height
 * Scales proportionally with viewport height, clamped to min/max.
 */
export function useViewportScale(): ViewportScaleResult {
  const calculateScale = useCallback(() => {
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const { rowHeight, scaleFactor } = resolveRowHeight(
      vh,
      BASE_VIEWPORT_HEIGHT,
      DEFAULT_ROW_HEIGHT,
      MIN_ROW_HEIGHT,
      MAX_ROW_HEIGHT
    );
    const aspectRatio = resolveAspectRatioLabel(vw, vh);

    return {
      rowHeight,
      scaleFactor,
      viewportHeight: vh,
      viewportWidth: vw,
      aspectRatio
    };
  }, []);

  const [scale, setScale] = useState<ViewportScaleResult>(calculateScale);
  useViewportScaleEffects({ calculateScale, setScale });

  return scale;
}
