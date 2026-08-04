import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    // The Python API. A proxy rather than CORS: one origin in development is one
    // origin in production, so nothing depends on a permission the deployed app
    // will not have.
    proxy: { "/api": { target: "http://127.0.0.1:8787", changeOrigin: true } },
  },
})
