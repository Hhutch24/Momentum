import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const { MOMENTUM_API_URL } = loadEnv(mode, '.', 'MOMENTUM_')
  const proxy = { '/api': MOMENTUM_API_URL || 'http://127.0.0.1:8000' }
  return {
    plugins: [react(), tailwindcss()],
    server: { proxy },
    preview: { proxy },
  }
})
