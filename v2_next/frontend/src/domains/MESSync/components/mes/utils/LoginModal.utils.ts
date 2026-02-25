import type { VerifyAuthResponse } from '../types/LoginModal.types';

const VERIFY_AUTH_ENDPOINT = '/api/mes/auth/verify';

export const verifyMesPassword = async (password: string): Promise<VerifyAuthResponse> => {
  const response = await fetch(VERIFY_AUTH_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ password }),
  });

  return response.json();
};
