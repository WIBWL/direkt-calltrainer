// Copies the VAD worklet, model and onnxruntime WASM into public/vad/ (gitignored, ~15MB).
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
  // Every wasm variant: the runtime picks what the browser needs.
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
