import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const allowedHosts = String(process.env.VITE_ALLOWED_HOSTS || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts,
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
