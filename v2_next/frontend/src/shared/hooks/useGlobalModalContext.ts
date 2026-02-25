import { useContext } from 'react';
import { ModalContext } from '../context/GlobalModalContext';

export const useGlobalModalContext = () => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a GlobalModalProvider');
  }
  return context;
};

export const useModal = useGlobalModalContext;
