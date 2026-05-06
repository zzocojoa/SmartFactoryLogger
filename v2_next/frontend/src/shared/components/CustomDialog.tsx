import React, { useEffect, useRef, useState } from 'react';
import { useGlobalModalContext } from '../hooks/useGlobalModalContext';

export const CustomDialog: React.FC = () => {
  const { state, close } = useGlobalModalContext();
  const inputRef = useRef<HTMLInputElement>(null);
  const didSubmitRef = useRef<boolean>(false);
  const [promptValue, setPromptValue] = useState<string>('');

  // 프롬프트가 열리면 입력창에 포커스
  useEffect(() => {
    didSubmitRef.current = false;
    setPromptValue(state.defaultValue ?? '');

    if (state.isOpen && state.type === 'prompt' && inputRef.current) {
      const timer = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [state.defaultValue, state.isOpen, state.modalId, state.type]);

  if (!state.isOpen) return null;

  const handleConfirm = (): void => {
    if (didSubmitRef.current) return;

    didSubmitRef.current = true;

    if (state.type === 'prompt') {
      close(promptValue);
    } else {
      close(true);
    }
  };

  const handleCancel = (): void => {
    if (didSubmitRef.current) return;

    didSubmitRef.current = true;

    if (state.type === 'prompt') {
      close(null);
    } else {
      close(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter') handleConfirm();
    if (e.key === 'Escape') handleCancel();
  };

  return (
    <div className="custom-modal-overlay">
      <div className="custom-modal-content">
        {state.title && (
          <div className="custom-modal-header">
            <div className="custom-modal-title">{state.title}</div>
          </div>
        )}
        <div className="custom-modal-body">
          {state.message}
          {state.type === 'prompt' && (
            <input
              ref={inputRef}
              type={state.inputType || 'text'}
              className="custom-modal-input"
              value={promptValue}
              onChange={(event) => setPromptValue(event.target.value)}
              onKeyDown={handleKeyDown}
            />
          )}
        </div>

        <div className="custom-modal-actions">
          {state.type !== 'alert' && (
            <button className="custom-modal-btn cancel" onClick={handleCancel}>
              취소
            </button>
          )}
          <button className="custom-modal-btn confirm" onClick={handleConfirm}>
            확인
          </button>
        </div>
      </div>
    </div>
  );
};
