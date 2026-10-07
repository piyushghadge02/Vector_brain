import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { viteSingleFile } from 'vite-plugin-singlefile'
import { defineConfig } from 'vite'

// Single-file output is only for the static demo preview build
// (VITE_DEMO_MODE=true); the normal build is unchanged.
const isDemoPreview = process.env.VITE_DEMO_MODE === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss(), ...(isDemoPreview ? [viteSingleFile()] : [])],
  server: {
    host: '0.0.0.0', // reachable from Docker Compose port mapping
    port: 5173,
    // Dev only: forward API calls to the backend so the app can use the
    // same-origin `/api` base URL it uses in production (nginx proxies
    // there). The demo preview never reaches this — it uses mock data.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
