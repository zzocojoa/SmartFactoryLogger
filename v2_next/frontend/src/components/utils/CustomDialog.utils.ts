import type { ModalState } from '../../types/GlobalModalContext.types';
import type { CustomDialogVariant } from '../types/CustomDialog.types';

export type CustomDialogKeyboardAction = 'confirm' | 'cancel' | 'none';

export const resolveCustomDialogVariant = (state: ModalState): CustomDialogVariant =>
  state.variant ?? 'info';

export const resolveCustomDialogTitle = (state: ModalState): string => {
  if (state.title) {
    return state.title;
  }

  switch (state.type) {
    case 'alert':
      return '알림';
    case 'confirm':
      return '확인';
    default:
      return '입력';
  }
};

export const resolveConfirmResult = (state: ModalState, inputValue: string): unknown => {
  if (state.type === 'prompt') {
    return inputValue;
  }

  if (state.type === 'confirm') {
    return true;
  }

  return undefined;
};

export const resolveCancelResult = (state: ModalState): unknown => {
  if (state.type === 'confirm') {
    return false;
  }

  if (state.type === 'prompt') {
    return null;
  }

  return undefined;
};

export const shouldRenderPromptInput = (state: ModalState): boolean => state.type === 'prompt';

export const shouldRenderCancelButton = (state: ModalState): boolean =>
  state.type === 'confirm' || state.type === 'prompt';

export const resolveRootKeyboardAction = (
  state: ModalState,
  key: string
): CustomDialogKeyboardAction => {
  if (key === 'Enter') {
    return 'confirm';
  }

  if (key === 'Escape') {
    return state.type === 'alert' ? 'confirm' : 'cancel';
  }

  return 'none';
};

export const resolvePromptKeyboardAction = (key: string): CustomDialogKeyboardAction => {
  if (key === 'Enter') {
    return 'confirm';
  }

  if (key === 'Escape') {
    return 'cancel';
  }

  return 'none';
};
