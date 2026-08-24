import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend never talks to MT5 or Binance directly. Every request goes to the
// read-only WAVERUN API, proxied here during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
});
