import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Используем .env из папки frontend (по умолчанию Vite читает из корня проекта)
  // Если нужно читать из корня проекта, раскомментируйте строку ниже:
  // envDir: resolve(__dirname, '..'),
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost',
        changeOrigin: true
      }
    }
  }
});

