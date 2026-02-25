import type React from 'react';

export interface AuthGuardProps {
  children: React.ReactNode;
}

export interface AuthGuardModel {
  checking: boolean;
  isAuthenticated: boolean;
  handleLoginSuccess: () => void;
}

export interface AuthGuardViewProps extends AuthGuardProps {
  model: AuthGuardModel;
}
