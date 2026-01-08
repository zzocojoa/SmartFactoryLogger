import axios from 'axios';

const getBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // Universal location check (works in Window and Worker)
  // eslint-disable-next-line no-restricted-globals
  const loc = typeof window !== 'undefined' ? window.location : self.location;
  if (loc && loc.protocol === 'file:') {
    return 'http://localhost:8000';
  }
  return '';
};

export const API_BASE = getBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});
