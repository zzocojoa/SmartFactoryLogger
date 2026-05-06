import React, { createContext, useState, useCallback, useRef } from 'react';
import {
  buildInitialModalState,
  buildModalState,
  normalizeModalOptions,
} from '../services/GlobalModalContext.service';
import type {
  ModalContextType,
  ModalOptions,
  ModalType,
} from '../types/GlobalModalContext.types';

export const ModalContext = createContext<ModalContextType | null>(null);

export const GlobalModalProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState(buildInitialModalState);

  const resolver = useRef<((value: unknown) => void) | null>(null);
  const modalIdRef = useRef<number>(0);

  const openModal = useCallback((type: ModalType, message: string, options: ModalOptions) => {
    modalIdRef.current += 1;
    setState(buildModalState(type, message, options, modalIdRef.current));

    return new Promise<unknown>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const alert = useCallback((message: string, options?: ModalOptions | string) => {
    return openModal<void>('alert', message, normalizeModalOptions(options));
  }, [openModal]);

  const confirm = useCallback((message: string, options?: ModalOptions | string) => {
    return openModal<boolean>('confirm', message, normalizeModalOptions(options));
  }, [openModal]);

  const prompt = useCallback((message: string, defaultValue?: string, options?: ModalOptions | string) => {
    const opts = normalizeModalOptions(options);
    return openModal<string | null>('prompt', message, { ...opts, defaultValue });
  }, [openModal]);

  const close = useCallback((result?: unknown) => {
    setState((prev) => ({ ...prev, isOpen: false }));
    if (resolver.current) {
      resolver.current(result);
      resolver.current = null;
    }
  }, []);

  const value = {
    alert,
    confirm,
    prompt,
    close,
    state,
  };

  return (
    <ModalContext.Provider value={value}>
      {children}
    </ModalContext.Provider>
  );
};

