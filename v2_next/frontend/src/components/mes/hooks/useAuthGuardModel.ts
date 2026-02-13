import { useCallback, useEffect, useState } from 'react';
import type { AuthGuardModel } from '../types/AuthGuard.types';
import { buildInitialAuthState } from '../utils/AuthGuard.utils';

export const useAuthGuardModel = (): AuthGuardModel => {
  const initialState = buildInitialAuthState();
  const [checking, setChecking] = useState(initialState.checking);
  const [isAuthenticated, setIsAuthenticated] = useState(initialState.isAuthenticated);

  useEffect(() => {
    // Always start as unauthenticated when mounted.
    setChecking(false);
  }, []);

  const handleLoginSuccess = useCallback(() => {
    setIsAuthenticated(true);
  }, []);

  return {
    checking,
    isAuthenticated,
    handleLoginSuccess,
  };
};
