import { useEffect } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { ViewportScaleResult } from './useViewportScale.types';

interface UseViewportScaleEffectsParams {
  calculateScale: () => ViewportScaleResult;
  setScale: Dispatch<SetStateAction<ViewportScaleResult>>;
}

export const useViewportScaleEffects = ({ calculateScale, setScale }: UseViewportScaleEffectsParams) => {
  useEffect(() => {
    const handleResize = () => {
      setScale(calculateScale());
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [calculateScale, setScale]);
};
