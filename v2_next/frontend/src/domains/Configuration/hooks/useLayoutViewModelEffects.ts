import { useEffect, useRef } from 'react';
import { useDashboardStore } from '../../../store/useDashboardStore';
import type { LayoutSnapshot } from '../../../shared/types';

interface UseLayoutViewModelEffectsParams {
  loadLayoutSnapshot: () => Promise<void>;
  layoutSnapshot: LayoutSnapshot | null;
}

export const useLayoutViewModelEffects = ({
  loadLayoutSnapshot,
  layoutSnapshot,
}: UseLayoutViewModelEffectsParams) => {
  const initialLoadStartedRef = useRef(false);
  const connected = useDashboardStore((state) => state.connected);
  const prevConnectedRef = useRef<boolean>(connected);

  useEffect(() => {
    if (initialLoadStartedRef.current) {
      return;
    }
    initialLoadStartedRef.current = true;
    void loadLayoutSnapshot();
  }, [loadLayoutSnapshot]);

  // Retry when the backend recovers after the initial layout fetch likely failed.
  useEffect(() => {
    const wasDisconnected = prevConnectedRef.current === false;
    prevConnectedRef.current = connected;

    if (connected && wasDisconnected && layoutSnapshot === null) {
      void loadLayoutSnapshot();
    }
  }, [connected, layoutSnapshot, loadLayoutSnapshot]);
};
