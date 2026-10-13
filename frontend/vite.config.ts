/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API runs separately on :8000; Vite proxies the API and media paths to it
// so cookies stay same-origin. In production Caddy does the same job.
const apiTarget = process.env.VITE_API_PROXY ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false },
      '/media': { target: apiTarget, changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router', '@tanstack/react-query'],
          mantine: ['@mantine/core', '@mantine/hooks', '@mantine/notifications'],
        },
      },
    },
  },
  test: {
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    environment: 'node',
  },
});
