import React from 'react';
import { AuthGuardView } from './components/AuthGuard.view';
import { useAuthGuardModel } from './hooks/useAuthGuardModel';
import type { AuthGuardProps } from './types/AuthGuard.types';

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const model = useAuthGuardModel();
  return <AuthGuardView model={model}>{children}</AuthGuardView>;
};
