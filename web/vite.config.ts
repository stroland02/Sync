import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: {
    // The Python API. A proxy rather than CORS: one origin in development is one
    // origin in production, so nothing depends on a permission the deployed app
    // will not have.
    proxy: { "/api": { target: "http://127.0.0.1:8787", changeOrigin: true } },
  },
  build: {
    // echarts is lazy-loaded into its own chunk (see corpus-summary.tsx) so it
    // never lands in the initial bundle; the default 500kB warning still fires
    // on that chunk alone because echarts itself is that large minified.
    chunkSizeWarningLimit: 1200,
  },
})
