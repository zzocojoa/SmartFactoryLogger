import type { ModalOptions, ModalState, ModalType } from '../types/GlobalModalContext.types';

export const buildInitialModalState = (): ModalState => ({
  isOpen: false,
  type: 'alert',
  message: '',
});

export const normalizeModalOptions = (options?: ModalOptions | string): ModalOptions => {
  if (typeof options === 'string') {
    return { title: options };
  }
  return options ?? {};
};

export const buildModalState = (
  type: ModalType,
  message: string,
  options: ModalOptions = {}
): ModalState => ({
  isOpen: true,
  type,
  message,
  title: options.title,
  defaultValue: options.defaultValue,
  variant: options.variant,
  inputType: options.inputType,
});
