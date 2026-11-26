import { defineConfig } from 'vite';

const bill = { target: 'http://localhost:8000', changeOrigin: true };
const split = { target: 'http://localhost:8001', changeOrigin: true };

export default defineConfig({
  server: {
    port: 8080,
    proxy: {
      '/api': split,
      '/bills': bill,
      '/tables': bill,
      '/dishes': bill,
      '/ingredients': bill,
      '/menu': bill,
    },
  },
});
