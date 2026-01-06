import { resolve } from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/stats': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: [
      { find: '@grafana/scenes', replacement: '@grafana/scenes/dist/index.js' },
      {
        find: /^react-router-dom$/,
        replacement: resolve(process.cwd(), 'src/shims/react-router-dom.ts'),
      },
    ],
  },
  define: {
    // Grafana libraries often check process.env
    'process.env': {},
  },
});
