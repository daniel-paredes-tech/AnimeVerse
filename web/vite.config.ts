/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API (`animeverse serve`) listens on 127.0.0.1:8000 and only accepts the Host
// `localhost` or `127.0.0.1`. The dev server forwards `/v1` to it and keeps the
// browser's Host header (no changeOrigin), so the UI calls the API same-origin and
// needs no CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/v1": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  build: {
    // The production server sends a strict CSP: no inline scripts or styles.
    assetsInlineLimit: 0,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
