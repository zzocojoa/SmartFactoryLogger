import { useEffect } from 'react';

interface UseSystemViewModelEffectsParams {
  reconnectBusy: boolean;
}

export const useSystemViewModelEffects = ({ reconnectBusy }: UseSystemViewModelEffectsParams) => {
  useEffect(() => {
    void reconnectBusy;
  }, [reconnectBusy]);
};
