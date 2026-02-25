import { useEffect } from 'react';

interface UseLayoutViewModelEffectsParams {
  loadLayoutSnapshot: () => Promise<void>;
}

export const useLayoutViewModelEffects = ({ loadLayoutSnapshot }: UseLayoutViewModelEffectsParams) => {
  useEffect(() => {
    void loadLayoutSnapshot();
  }, [loadLayoutSnapshot]);
};
