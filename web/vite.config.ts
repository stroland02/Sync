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
    //
    // `SYNC_API_ORIGIN` overrides the default because several agents share this machine and
    // 8787 is routinely held — sometimes by a process that has died and left the port bound,
    // which answers nothing and cannot be killed. Every session that hit this edited this line
    // and was then expected to revert it before committing, which is a tracked file mutated for
    // a local condition and exactly the kind of edit that gets committed by accident.
    proxy: {
      "/api": {
        target: process.env.SYNC_API_ORIGIN ?? "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
  build: {
    // echarts is lazy-loaded into its own chunk (see corpus-summary.tsx) so it
    // never lands in the initial bundle; the default 500kB warning still fires
    // on that chunk alone because echarts itself is that large minified.
    chunkSizeWarningLimit: 1200,
  },
})
