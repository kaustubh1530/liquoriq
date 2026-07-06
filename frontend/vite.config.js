import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth':      'http://localhost:8000',
      '/stores':    'http://localhost:8000',
      '/uploads':   'http://localhost:8000',
      '/analytics': 'http://localhost:8000',
      '/ai':        'http://localhost:8000',
      '/creative':  'http://localhost:8000',
      '/static':    'http://localhost:8000',
      '/reports':   'http://localhost:8000',
    },
  },
})
