import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/generate/ws": {
        target: "ws://localhost:8080",
        ws: true,
        changeOrigin: true,
      },
      "/generate-from-context": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
      "/generate": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
});
