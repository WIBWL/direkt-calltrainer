import { MicVAD } from "@ricky0123/vad-web";
import { useCallback, useEffect, useRef, useState } from "react";

import { encodeWav } from "../utils/wav";

const SAMPLE_RATE = 16000;

/**
 * Arms the microphone on demand and automatically finalizes a Turn once the
 * user stops speaking — automatic turn-taking, no manual "stop recording"
 * control. Backed by Silero VAD, running fully in-browser via
 * @ricky0123/vad-web (ONNX + WASM, assets served from /vad/, see
 * scripts/copy-vad-assets.mjs) — a real trained speech/non-speech model
 * instead of a hand-rolled amplitude threshold, which proved too unreliable
 * (missed or badly-timed end-of-speech detection).
 */
export function useMicrophoneVAD(onTurnAudio: (blob: Blob, mimeType: string) => void) {
  const [micError, setMicError] = useState<string | null>(null);
  const vadRef = useRef<Awaited<ReturnType<typeof MicVAD.new>> | null>(null);
  const initRef = useRef<Promise<void> | null>(null);

  const ensureVad = useCallback(async () => {
    if (!initRef.current) {
      initRef.current = MicVAD.new({
        baseAssetPath: "/vad/",
        onnxWASMBasePath: "/vad/",
        startOnLoad: false,
        onSpeechStart: () => console.debug("[VAD] speech start"),
        onVADMisfire: () => console.debug("[VAD] misfire (too short, ignored)"),
        onSpeechEnd: (audio: Float32Array) => {
          console.debug("[VAD] speech end, samples:", audio.length);
          void vadRef.current?.pause();
          onTurnAudio(encodeWav(audio, SAMPLE_RATE), "audio/wav");
        },
      })
        .then((vad) => {
          vadRef.current = vad;
        })
        .catch((e: Error) => {
          setMicError(e.message);
        });
    }
    await initRef.current;
  }, [onTurnAudio]);

  // Fire-and-forget: starts fetching/initializing the ~15MB VAD model in the
  // background (e.g. during mic-check) so it's already warm by the time
  // startListening() is actually needed — the model load, not the mic
  // permission prompt, is the slow part.
  const preload = useCallback(() => {
    void ensureVad();
  }, [ensureVad]);

  const startListening = useCallback(async () => {
    await ensureVad();
    await vadRef.current?.start();
  }, [ensureVad]);

  const stopListening = useCallback(() => {
    void vadRef.current?.pause();
  }, []);

  useEffect(() => {
    return () => {
      void vadRef.current?.destroy();
    };
  }, []);

  return { preload, startListening, stopListening, micError };
}
