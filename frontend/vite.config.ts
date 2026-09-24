/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: "../",
  // The SPA reads OIDC_ISSUER under the backend's own name, not a VITE_ copy,
  // so the two cannot drift. OIDC_JWKS_URL is runtime-only, never in the build.
  envPrefix: ["VITE_", "OIDC_"],
  server: {
    port: 5173,
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
  // scripts/copy-vad-assets.mjs). `vite build` is unaffected — test VAD changes
  // against the production build.
});
