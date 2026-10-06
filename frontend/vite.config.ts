/// <reference types="vitest/config" />
import type { IncomingMessage, ServerResponse } from "node:http";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** /config.js in dev and preview, as docker/render-config.sh writes it in the image. */
function runtimeConfig(): Plugin {
  const serveConfig = (_req: IncomingMessage, res: ServerResponse) => {
    const config = { oidcIssuer: process.env.OIDC_ISSUER };
    res.setHeader("Content-Type", "text/javascript");
    res.setHeader("Cache-Control", "no-store");
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

// One origin locally, so no CORS.
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
  // 5173 and 8391 are the dev realm's redirect URIs.
  preview: {
    port: 8391,
    strictPort: true,
    proxy,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  // Known gap: `npm run dev` 500s on onnxruntime-web's .mjs glue; test calls on build:watch + preview.
});
