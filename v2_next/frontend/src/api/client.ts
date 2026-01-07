import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || (window.location.protocol.startsWith('file') ? 'http://localhost:8000' : '');

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});
