import { useCallback, useEffect, useRef, useState } from 'react';
import { useModal } from '../../hooks/useGlobalModalContext';
import type { CustomDialogModel } from '../types/CustomDialog.types';
import {
  resolveCancelResult,
  resolveConfirmResult,
  resolveCustomDialogTitle,
  resolveCustomDialogVariant,
  resolvePromptKeyboardAction,
  resolveRootKeyboardAction,
  shouldRenderCancelButton,
  shouldRenderPromptInput,
} from '../utils/CustomDialog.utils';

export const useCustomDialogModel = (): CustomDialogModel => {
  const { state, close } = useModal();
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!state.isOpen) {
      return;
    }

    setInputValue(state.defaultValue ?? '');

    if (state.type !== 'prompt') {
      return;
    }

    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 100);
    return () => window.clearTimeout(focusTimer);
  }, [state.defaultValue, state.isOpen, state.type]);

  const handleConfirm = useCallback(() => {
    close(resolveConfirmResult(state, inputValue));
  }, [close, inputValue, state]);

  const handleCancel = useCallback(() => {
    close(resolveCancelResult(state));
  }, [close, state]);

  const handleRootKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const action = resolveRootKeyboardAction(state, event.key);
      if (action === 'confirm') {
        handleConfirm();
      } else if (action === 'cancel') {
        handleCancel();
      }
    },
    [handleCancel, handleConfirm, state]
  );

  const handleInputKeyDown = useCallback((event: React.KeyboardEvent<HTMLInputElement>) => {
    event.stopPropagation();
  }, []);

  const handleInputKeyUp = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      const action = resolvePromptKeyboardAction(event.key);
      if (action === 'confirm') {
        handleConfirm();
      } else if (action === 'cancel') {
        handleCancel();
      }
    },
    [handleCancel, handleConfirm]
  );

  const handleInputChange = useCallback((value: string) => {
    setInputValue(value);
  }, []);

  return {
    state,
    isOpen: state.isOpen,
    variant: resolveCustomDialogVariant(state),
    inputValue,
    inputRef,
    shouldRenderPromptInput: shouldRenderPromptInput(state),
    shouldRenderCancelButton: shouldRenderCancelButton(state),
    dialogTitle: resolveCustomDialogTitle(state),
    handleInputChange,
    handleConfirm,
    handleCancel,
    handleRootKeyDown,
    handleInputKeyDown,
    handleInputKeyUp,
  };
};
