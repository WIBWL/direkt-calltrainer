/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: "../",
  server: {
    port: 5173,
  },
  // The automated frontend tests, and they are two narrow things rather than
  // a component-test setup: the live-call audio path, whose barge-in races are
  // invisible to `tsc` and impossible to catch by hand reliably (see
  // useStreamedAudioPlayback / useSessionSocket / useBargeIn specs), and the
  // pure decision tables under them (trainingFlow). jsdom plus hand-written
  // Web Audio / WebSocket fakes, nothing more. `stylesheet.test.ts` is the one
  // exception and renders nothing at all — it reads index.css and the source
  // as text, because one sheet for 74 components outlives the markup that
  // needed it and nothing else would say so.
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
