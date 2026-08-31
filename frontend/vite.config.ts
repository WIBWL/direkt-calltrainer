import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: "../",
  server: {
    port: 5173,
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
