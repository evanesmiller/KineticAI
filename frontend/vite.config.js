import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth':       'http://127.0.0.1:5000',
      '/workouts':   'http://127.0.0.1:5000',
      '/exercises':  'http://127.0.0.1:5000',
      '/fatigue':    'http://127.0.0.1:5000',
      '/evaluation': 'http://127.0.0.1:5000',
      '/api':        'http://127.0.0.1:5000',
      '/health':     'http://127.0.0.1:5000',
    },
  },
})
