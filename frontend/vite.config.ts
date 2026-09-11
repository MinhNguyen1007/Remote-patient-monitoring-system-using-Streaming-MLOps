/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/postcss';
import { fileURLToPath } from 'node:url';

// Backend FastAPI chạy ở cổng 8000. Frontend gọi qua /api (REST và WebSocket) để không vướng CORS
// giữa 127.0.0.1 và localhost; bản build Docker dùng cùng tiền tố /api qua nginx.
const BACKEND = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true, ws: true, rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  css: { postcss: { plugins: [tailwindcss()] } },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
