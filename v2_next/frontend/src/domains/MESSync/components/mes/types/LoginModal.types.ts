import type React from 'react';

export interface LoginModalProps {
  onLogin: () => void;
}

export interface VerifyAuthResponse {
  success: boolean;
  message?: string;
}

export interface LoginModalModel {
  password: string;
  error: string | null;
  loading: boolean;
  inputRef: React.RefObject<HTMLInputElement>;
  handlePasswordChange: (value: string) => void;
  handleSubmit: (event?: React.FormEvent) => Promise<void>;
}

export interface LoginModalViewProps {
  model: LoginModalModel;
}
