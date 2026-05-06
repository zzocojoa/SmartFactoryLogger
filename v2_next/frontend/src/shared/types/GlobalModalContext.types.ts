export type ModalType = 'alert' | 'confirm' | 'prompt';

export interface ModalOptions {
  title?: string;
  defaultValue?: string;
  variant?: 'info' | 'warning' | 'error' | 'success';
  inputType?: 'text' | 'password';
}

export interface ModalState {
  isOpen: boolean;
  type: ModalType;
  message: string;
  modalId: number;
  title?: string;
  defaultValue?: string;
  variant?: 'info' | 'warning' | 'error' | 'success';
  inputType?: 'text' | 'password';
}

export interface ModalContextType {
  alert: (message: string, options?: ModalOptions | string) => Promise<void>;
  confirm: (message: string, options?: ModalOptions | string) => Promise<boolean>;
  prompt: (message: string, defaultValue?: string, options?: ModalOptions | string) => Promise<string | null>;
  close: (result?: unknown) => void;
  state: ModalState;
}
