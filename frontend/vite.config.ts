/// <reference types="vitest/config" />
import type { IncomingMessage, ServerResponse } from "node:http";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Serves /config.js in dev and preview, like docker/render-config.sh does in
 * the image. Reads the same OIDC_ISSUER as the backend, from the shell Vite
 * was started in (`source .env`). Restart after editing .env.
 */
function runtimeConfig(): Plugin {
  const serveConfig = (_req: IncomingMessage, res: ServerResponse) => {
    const config = { oidcIssuer: process.env.OIDC_ISSUER };
    res.setHeader("Content-Type", "text/javascript");
    res.setHeader("Cache-Control", "no-store");
    // An unset issuer is omitted, so src/config.ts refuses to start and says why.
    res.end(`window.__APP_CONFIG__ = ${JSON.stringify(config)};\n`);
  };

  return {
    name: "calltrainer:runtime-config",
    configureServer(server) {
      server.middlewares.use("/config.js", serveConfig);
    },
    configurePreviewServer(server) {
      server.middlewares.use("/config.js", serveConfig);
    },
  };
}

// The backend on the host (`uvicorn`), under the SPA's own origin, so the
// browser needs no CORS locally. `ws` carries the live call's socket.
const proxy = {
  "/api": { target: "http://localhost:8000" },
  "/ws": { target: "http://localhost:8000", ws: true },
  "/health": { target: "http://localhost:8000" },
};

export default defineConfig({
  plugins: [react(), runtimeConfig()],
  server: {
    port: 5173,
    proxy,
  },
  // The production build, where VAD works (see the note at the bottom). 8391 is
  // the port Keycloak's redirect URIs name, like 5173 for the dev server.
  preview: {
    port: 8391,
    strictPort: true,
    proxy,
  },
  // Deliberately narrow tests, not a component-test setup: the live-call audio
  // path's barge-in races, and pure functions (trainingFlow, utils/). jsdom plus
  // hand-written Web Audio / WebSocket fakes (src/test/setup.ts).
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  // Known gap: under `npm run dev`, Vite 5's import-analysis 500s on
  // onnxruntime-web's dynamically imported .mjs WASM glue (from /vad/, see
  // scripts/copy-vad-assets.mjs). `vite build` is unaffected — run a call
  // against `npm run build:watch` plus `npm run preview`.
});
