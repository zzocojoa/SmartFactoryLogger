import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      '@grafana/scenes': '@grafana/scenes/dist/index.js',
    },
  },
  define: {
    // Grafana libraries often check process.env
    'process.env': {},
  },
});
