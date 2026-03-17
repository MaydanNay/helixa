import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
    },
    strictPort: true,
    hmr: {
      clientPort: 5173,
    },
    proxy: {
      '/api': {
        target: 'http://api:8005',
        changeOrigin: true,
      }
    }
  }
})
