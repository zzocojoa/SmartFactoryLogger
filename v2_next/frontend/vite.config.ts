import { resolve } from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
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
