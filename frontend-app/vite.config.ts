import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API serves the built app at /app/ (backend/app/main.py, docs/deploy.md).
// Without this base, built assets are requested from /assets/... and 404 in production.
const BASE = "/app/";

export default defineConfig({
  base: BASE,
  plugins: [react()],
  server: {
    port: 5173,
    // The glossary (pages/Learn.tsx) and practice cards (practices.ts) are imported from backend/data.
    fs: { allow: [".", "../backend/data"] },
    // In dev, everything outside /app/ goes to the API (make dev on :8000).
    // The browser sees one origin, as in production, so no CORS and the same relative URLs.
    proxy: {
      "^/(?!app(/|$)).*": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
