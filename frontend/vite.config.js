import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  envDir: '..',
  server: {
    port: 5173,
    proxy: {
      '/users': { target: 'http://localhost:8000', changeOrigin: true },
      '/events': { target: 'http://localhost:8000', changeOrigin: true },
      '/venues': { target: 'http://localhost:8000', changeOrigin: true },
      '/equipment': { target: 'http://localhost:8000', changeOrigin: true },
      '/registrations': { target: 'http://localhost:8000', changeOrigin: true },
      '/notifications': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
