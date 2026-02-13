import React from 'react';
import type { CustomDialogVariant, CustomDialogViewProps } from '../types/CustomDialog.types';

const DialogIcon: React.FC<{ variant: CustomDialogVariant }> = ({ variant }) => {
  switch (variant) {
    case 'warning':
      return (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'var(--state-warn)' }}
        >
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      );
    case 'error':
      return (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'var(--state-danger)' }}
        >
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="15" y1="9" x2="9" y2="15"></line>
          <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>
      );
    case 'success':
      return (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'var(--state-ok)' }}
        >
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
      );
    default:
      return (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'var(--accent-main)' }}
        >
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
      );
  }
};

export const CustomDialogView: React.FC<CustomDialogViewProps> = ({ model }) => {
  const {
    state,
    variant,
    inputRef,
    inputValue,
    dialogTitle,
    shouldRenderPromptInput,
    shouldRenderCancelButton,
    handleRootKeyDown,
    handleInputChange,
    handleInputKeyDown,
    handleInputKeyUp,
    handleCancel,
    handleConfirm,
  } = model;

  return (
    <div className="custom-modal-overlay">
      <div className={`custom-modal-content ${variant}`} onKeyDown={handleRootKeyDown} tabIndex={-1}>
        <div className="custom-modal-header">
          <div className="custom-modal-icon-wrapper">
            <DialogIcon variant={variant} />
          </div>
          <span className={`custom-modal-title ${variant}`}>{dialogTitle}</span>
        </div>
        <div className="custom-modal-body">
          <p>{state.message}</p>
          {shouldRenderPromptInput && (
            <input
              ref={inputRef}
              type={state.inputType ?? 'text'}
              className="custom-modal-input"
              value={inputValue}
              onChange={(event) => handleInputChange(event.target.value)}
              onKeyDown={handleInputKeyDown}
              onKeyUp={handleInputKeyUp}
            />
          )}
        </div>
        <div className="custom-modal-actions">
          {shouldRenderCancelButton && (
            <button className="custom-modal-btn cancel" onClick={handleCancel}>
              취소
            </button>
          )}
          <button className={`custom-modal-btn confirm ${variant}`} onClick={handleConfirm}>
            확인
          </button>
        </div>
      </div>
    </div>
  );
};
