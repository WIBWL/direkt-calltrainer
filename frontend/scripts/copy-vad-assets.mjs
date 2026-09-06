// Copies @ricky0123/vad-web's worklet+model and onnxruntime-web's WASM
// runtime into public/vad/, so Vite serves them as static files (dev) and
// bundles them into dist/ as-is (build) — these are large binary assets
// (~15-20MB) fetched by the browser at runtime, not meant to be bundled by
// the JS bundler or committed to git (see .gitignore).
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const outDir = join(root, "public", "vad");

const vadWebDist = join(root, "node_modules", "@ricky0123", "vad-web", "dist");
const ortWebDist = join(root, "node_modules", "onnxruntime-web", "dist");

const files = [
  [vadWebDist, "vad.worklet.bundle.min.js"],
  [vadWebDist, "silero_vad_legacy.onnx"], // default model (see real-time-vad.js DEFAULT_MODEL)
  // All wasm variants, so the runtime's own feature detection (SIMD/threads/
  // JSEP/JSPI) can pick whichever this browser needs — a browser only
  // downloads the specific file(s) it actually requests.
  [ortWebDist, "ort-wasm-simd-threaded.wasm"],
  [ortWebDist, "ort-wasm-simd-threaded.mjs"],
  [ortWebDist, "ort-wasm-simd-threaded.asyncify.wasm"],
  [ortWebDist, "ort-wasm-simd-threaded.asyncify.mjs"],
  [ortWebDist, "ort-wasm-simd-threaded.jsep.wasm"],
  [ortWebDist, "ort-wasm-simd-threaded.jsep.mjs"],
  [ortWebDist, "ort-wasm-simd-threaded.jspi.wasm"],
  [ortWebDist, "ort-wasm-simd-threaded.jspi.mjs"],
];

mkdirSync(outDir, { recursive: true });

let copied = 0;
for (const [srcDir, name] of files) {
  const src = join(srcDir, name);
  if (!existsSync(src)) {
    console.warn(`[copy-vad-assets] skipping missing file: ${src}`);
    continue;
  }
  copyFileSync(src, join(outDir, name));
  copied += 1;
}

console.log(`[copy-vad-assets] copied ${copied}/${files.length} files to ${outDir}`);
