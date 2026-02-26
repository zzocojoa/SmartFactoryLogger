import React, { useRef, useEffect } from 'react';
import { useGlobalModalContext } from '../hooks/useGlobalModalContext';

export const CustomDialog: React.FC = () => {
  const { state, close } = useGlobalModalContext();
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on mount if prompt
  useEffect(() => {
    if (state.isOpen && state.type === 'prompt' && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [state.isOpen, state.type]);

  if (!state.isOpen) return null;

  const handleConfirm = () => {
    if (state.type === 'prompt') {
      close(inputRef.current?.value || '');
    } else {
      close(true);
    }
  };

  const handleCancel = () => {
    if (state.type === 'prompt') {
      close(null);
    } else {
      close(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
              defaultValue={state.defaultValue || ''}
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
