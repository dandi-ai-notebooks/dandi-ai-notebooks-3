import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/dandi-ai-notebooks-3/',
  plugins: [react()],
  server: {
    port: 3000,
    open: true
  }
})
