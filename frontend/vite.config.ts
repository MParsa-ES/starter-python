import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // The backend address stays out of the code: the browser calls /api and Vite forwards it.
    proxy: { '/api': 'http://localhost:8084' },
  },
})
