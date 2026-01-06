import { resolve } from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_BASE_URL || 'http://localhost:8000';

  return {
    base: './',
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/stats': {
          target: apiTarget,
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
  };
});
