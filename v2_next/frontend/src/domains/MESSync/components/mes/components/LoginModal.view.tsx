import React from 'react';
import type { LoginModalViewProps } from '../types/LoginModal.types';

export const LoginModalView: React.FC<LoginModalViewProps> = ({ model }) => {
  const { password, error, loading, inputRef, handlePasswordChange, handleSubmit } = model;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.98))',
        zIndex: 9999,
        animation: 'fadeIn 0.5s ease-out',
      }}
    >
      <style>
        {`
          @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
          @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
          @keyframes glow {
            0% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.5); }
            50% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.8), 0 0 10px rgba(59, 130, 246, 0.4) inset; }
            100% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.5); }
          }
          @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
          .glass-card {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          }
          .login-input {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
            transition: all 0.3s ease;
          }
          .login-input:focus {
            outline: none;
            border-color: #3b82f6;
            background: rgba(0, 0, 0, 0.5);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
          }
          .login-btn {
            background: linear-gradient(to right, #3b82f6, #2563eb);
            transition: all 0.3s ease;
          }
          .login-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
          }
          .login-btn:active {
            transform: translateY(0);
          }
          .login-btn:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
          }
        `}
      </style>

      <div
        className="glass-card"
        style={{
          width: '100%',
          maxWidth: '420px',
          padding: '3rem 2rem',
          borderRadius: '1.5rem',
          animation: 'slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: '-50px',
            left: '-50px',
            width: '150px',
            height: '150px',
            background: 'radial-gradient(circle, rgba(59,130,246,0.2) 0%, transparent 70%)',
            borderRadius: '50%',
            filter: 'blur(20px)',
          }}
        />

        <div
          style={{
            width: '64px',
            height: '64px',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '1.5rem',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: '0 0 15px rgba(59, 130, 246, 0.1)',
          }}
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
        </div>

        <h2
          style={{
            color: '#fff',
            fontSize: '1.75rem',
            fontWeight: 600,
            marginBottom: '0.5rem',
            letterSpacing: '-0.5px',
          }}
        >
          Welcome Back
        </h2>

        <p
          style={{
            color: '#94a3b8',
            fontSize: '0.95rem',
            marginBottom: '2.5rem',
            textAlign: 'center',
          }}
        >
          Enter your access credential to view the dashboard
        </p>

        <form onSubmit={handleSubmit} style={{ width: '100%' }}>
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ position: 'relative' }}>
              <input
                ref={inputRef}
                type="password"
                className="login-input"
                value={password}
                onChange={(event) => handlePasswordChange(event.target.value)}
                placeholder="Enter Access Password"
                style={{
                  width: '100%',
                  padding: '14px 16px',
                  paddingLeft: '46px',
                  paddingRight: '46px',
                  borderRadius: '12px',
                  fontSize: '1rem',
                  letterSpacing: '0.2rem',
                  boxSizing: 'border-box',
                }}
              />

              <div style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
              </div>

              <button
                type="submit"
                style={{
                  position: 'absolute',
                  right: '8px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: password ? '#3b82f6' : '#475569',
                  display: 'flex',
                  padding: '8px',
                  transition: 'color 0.2s',
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                  <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
              </button>
            </div>
          </div>

          {error && (
            <div
              style={{
                color: '#ef4444',
                marginBottom: '1.5rem',
                fontSize: '0.9rem',
                textAlign: 'center',
                background: 'rgba(239, 68, 68, 0.1)',
                padding: '8px',
                borderRadius: '8px',
                border: '1px solid rgba(239, 68, 68, 0.2)',
              }}
            >
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            className="login-btn"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '12px',
              fontSize: '1rem',
              fontWeight: 600,
              color: 'white',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            {loading ? (
              <>
                <span
                  className="spinner"
                  style={{
                    width: '18px',
                    height: '18px',
                    border: '2px solid rgba(255,255,255,0.3)',
                    borderTop: '2px solid white',
                    borderRadius: '50%',
                    display: 'inline-block',
                    animation: 'spin 1s linear infinite',
                  }}
                />
                Verifying...
              </>
            ) : (
              'Access Dashboard'
            )}
          </button>
        </form>
      </div>

      <div
        style={{
          position: 'absolute',
          bottom: '2rem',
          color: 'rgba(255,255,255,0.2)',
          fontSize: '0.8rem',
        }}
      >
        Protected System - Authorized Personnel Only
      </div>
    </div>
  );
};
