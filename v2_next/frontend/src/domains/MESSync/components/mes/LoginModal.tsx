import React from 'react';
import { LoginModalView } from './components/LoginModal.view';
import { useLoginModalModel } from './hooks/useLoginModalModel';
import type { LoginModalProps } from './types/LoginModal.types';

export const LoginModal: React.FC<LoginModalProps> = (props) => {
  const model = useLoginModalModel(props);
  return <LoginModalView model={model} />;
};
