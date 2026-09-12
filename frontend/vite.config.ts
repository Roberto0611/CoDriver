import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import compression from 'compression'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Comprimir respuestas del dev server (JSON de 63 MB → ~12 MB por red)
    {
      name: 'dev-gzip',
      configureServer(server) {
        server.middlewares.use(compression() as Parameters<typeof server.middlewares.use>[0])
      },
    },
  ],
})
