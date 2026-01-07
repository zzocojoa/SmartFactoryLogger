import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

type ModalType = 'alert' | 'confirm' | 'prompt';

interface ModalOptions {
  title?: string;
  defaultValue?: string;
  variant?: 'info' | 'warning' | 'error' | 'success';
  inputType?: 'text' | 'password';
}

interface ModalContextType {
  alert: (message: string, options?: ModalOptions | string) => Promise<void>;
  confirm: (message: string, options?: ModalOptions | string) => Promise<boolean>;
  prompt: (message: string, defaultValue?: string, options?: ModalOptions | string) => Promise<string | null>;
  close: (result?: any) => void;
  state: ModalState;
}

interface ModalState {
  isOpen: boolean;
  type: ModalType;
  message: string;
  title?: string;
  defaultValue?: string;
  variant?: 'info' | 'warning' | 'error' | 'success';
  inputType?: 'text' | 'password';
}

const ModalContext = createContext<ModalContextType | null>(null);

export const useModal = () => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a GlobalModalProvider');
  }
  return context;
};

export const GlobalModalProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<ModalState>({
    isOpen: false,
    type: 'alert',
    message: '',
  });

  const resolver = useRef<((value: any) => void) | null>(null);

  const openModal = useCallback((type: ModalType, message: string, options: ModalOptions = {}) => {
    setState({
      isOpen: true,
      type,
      message,
      title: options.title,
      defaultValue: options.defaultValue,
      variant: options.variant,
      inputType: options.inputType,
    });

    return new Promise<any>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const alert = useCallback((message: string, options?: ModalOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    return openModal('alert', message, opts);
  }, [openModal]);

  const confirm = useCallback((message: string, options?: ModalOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    return openModal('confirm', message, opts);
  }, [openModal]);

  const prompt = useCallback((message: string, defaultValue?: string, options?: ModalOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    return openModal('prompt', message, { ...opts, defaultValue });
  }, [openModal]);

  const close = useCallback((result?: any) => {
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
