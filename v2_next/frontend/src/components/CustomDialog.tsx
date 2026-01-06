import React, { useState, useEffect, useRef } from 'react';
import { useModal } from '../GlobalModalContext';

export const CustomDialog: React.FC = () => {
  const { state, close } = useModal();
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (state.isOpen) {
      setInputValue(state.defaultValue || '');
      // Focus input if prompt
      if (state.type === 'prompt') {
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    }
  }, [state.isOpen, state.defaultValue, state.type]);

  if (!state.isOpen) return null;

  const handleConfirm = () => {
    if (state.type === 'prompt') {
      close(inputValue);
    } else if (state.type === 'confirm') {
      close(true);
    } else {
      close();
    }
  };

  const handleCancel = () => {
    if (state.type === 'confirm') {
      close(false);
    } else if (state.type === 'prompt') {
      close(null);
    } else {
      close();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleConfirm();
    } else if (e.key === 'Escape') {
      if (state.type === 'alert') {
        handleConfirm();
      } else {
        handleCancel();
      }
    }
  };

  const variant = state.variant || 'info';

  const getIcon = () => {
    switch (variant) {
      case 'warning':
        return (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#f2c94c' }}>
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        );
      case 'error':
        return (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#f66b6b' }}>
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
        );
      case 'success':
        return (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#25c49a' }}>
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        );
      default: // info
        return (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#56a6dc' }}>
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
        );
    }
  };

  return (
    <div className="custom-modal-overlay">
      <div 
        className={`custom-modal-content ${variant}`}
        onKeyDown={handleKeyDown}
        tabIndex={-1}
      >
        <div className="custom-modal-header">
          <div className="custom-modal-icon-wrapper">
            {getIcon()}
          </div>
          <span className={`custom-modal-title ${variant}`}>
             {state.title || (state.type === 'alert' ? '알림' : state.type === 'confirm' ? '확인' : '입력')}
          </span>
        </div>
        <div className="custom-modal-body">
          <p>{state.message}</p>
          {state.type === 'prompt' && (
            <input
              ref={inputRef}
              type="text"
              className="custom-modal-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.stopPropagation()}
              onKeyUp={(e) => {
                if(e.key === 'Enter') handleConfirm();
                if(e.key === 'Escape') handleCancel();
              }}
            />
          )}
        </div>
        <div className="custom-modal-actions">
          {(state.type === 'confirm' || state.type === 'prompt') && (
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
