import axios from 'axios';
import { resolveApiBaseUrl } from './client.mapper';
import { getRuntimeLocation } from './transport/client.transport';

const getBaseUrl = () => {
  const loc = getRuntimeLocation();
  return resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL, loc, typeof window !== 'undefined');
};

export const API_BASE = getBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});
