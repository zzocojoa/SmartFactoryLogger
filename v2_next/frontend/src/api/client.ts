import axios from 'axios';

const getBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  
  // Check if running in production EXE mode
  // In Worker context, self.location.origin will be the backend server
  // eslint-disable-next-line no-restricted-globals
  const loc = typeof window !== 'undefined' ? window.location : self.location;
  
  // If main window is file://, it's EXE mode
  if (loc.protocol === 'file:') {
    return 'http://localhost:8000';
  }
  
  // Worker fallback: if we're in a worker and origin is localhost:8000, assume EXE mode
  // This handles the case where the worker is loaded from the backend static files
  if (typeof window === 'undefined' && loc.origin && loc.origin.includes('localhost:8000')) {
    return 'http://localhost:8000';
  }
  
  // Development mode - use relative paths (Vite proxy handles /api)
  return '';
};

export const API_BASE = getBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});
