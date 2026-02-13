import type React from 'react';
import type { ModalState } from '../../types/GlobalModalContext.types';

export type CustomDialogVariant = NonNullable<ModalState['variant']> | 'info';

export interface CustomDialogModel {
  state: ModalState;
  isOpen: boolean;
  variant: CustomDialogVariant;
  inputValue: string;
  inputRef: React.RefObject<HTMLInputElement>;
  shouldRenderPromptInput: boolean;
  shouldRenderCancelButton: boolean;
  dialogTitle: string;
  handleInputChange: (value: string) => void;
  handleConfirm: () => void;
  handleCancel: () => void;
  handleRootKeyDown: (event: React.KeyboardEvent) => void;
  handleInputKeyDown: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  handleInputKeyUp: (event: React.KeyboardEvent<HTMLInputElement>) => void;
}

export interface CustomDialogViewProps {
  model: CustomDialogModel;
}
