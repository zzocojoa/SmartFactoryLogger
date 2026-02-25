import { useCallback, useEffect, useRef, useState } from 'react';
import type { LoginModalModel, LoginModalProps } from '../types/LoginModal.types';
import { verifyMesPassword } from '../utils/LoginModal.utils';

export const useLoginModalModel = ({ onLogin }: LoginModalProps): LoginModalModel => {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 100);
    return () => window.clearTimeout(focusTimer);
  }, []);

  const handlePasswordChange = useCallback((value: string) => {
    setPassword(value);
  }, []);

  const handleSubmit = useCallback(
    async (event?: React.FormEvent) => {
      if (event) {
        event.preventDefault();
      }

      if (!password) {
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const data = await verifyMesPassword(password);
        if (data.success) {
          onLogin();
        } else {
          setError(data.message || 'Incorrect Password');
        }
      } catch {
        setError('Connection failed');
      } finally {
        setLoading(false);
      }
    },
    [onLogin, password]
  );

  return {
    password,
    error,
    loading,
    inputRef,
    handlePasswordChange,
    handleSubmit,
  };
};
