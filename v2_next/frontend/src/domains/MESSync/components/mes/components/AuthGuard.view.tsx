import React from 'react';
import { LoginModal } from '../LoginModal';
import type { AuthGuardViewProps } from '../types/AuthGuard.types';

export const AuthGuardView: React.FC<AuthGuardViewProps> = ({ children, model }) => {
  const { checking, isAuthenticated, handleLoginSuccess } = model;

  if (checking) {
    return null;
  }

  if (!isAuthenticated) {
    return <LoginModal onLogin={handleLoginSuccess} />;
  }

  return <>{children}</>;
};
