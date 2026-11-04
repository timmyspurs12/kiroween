import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build straight into app/web_dist so the stdlib Python server can serve the
// whole product from one process: `python3 app/server.py`.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../app/web_dist",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    host: true,
    allowedHosts: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8747",
        changeOrigin: false,
      },
    },
  },
});
