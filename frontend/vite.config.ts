/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: "../",
  server: {
    port: 5173,
  },
  // The only automated frontend tests: the live-call audio path, whose
  // barge-in races are invisible to `tsc` and impossible to catch by hand
  // reliably (see useStreamedAudioPlayback / useSessionSocket specs). Not a
  // general component-test setup — jsdom plus hand-written Web Audio / Web
  // Socket fakes, nothing more.
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  // @ricky0123/vad-web (Silero VAD) must stay prebundled — it's CJS-only, so
  // Vite's dev server can't resolve its named exports otherwise. Its
  // transitive onnxruntime-web dependency dynamically imports its own .mjs
  // WASM glue at runtime (from /vad/, see scripts/copy-vad-assets.mjs); Vite
  // 5's dev-server import-analysis currently 500s on that specific dynamic
  // import (a known dev-only onnxruntime-web/Vite interaction — the
  // production build via `vite build` is unaffected and works correctly).
  // No fix found yet for `npm run dev` itself; test VAD changes against a
  // production build (`npm run build`, served by the backend) in the
  // meantime.
});
