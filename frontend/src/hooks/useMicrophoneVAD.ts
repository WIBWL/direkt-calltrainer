import { MicVAD } from "@ricky0123/vad-web";
import { useCallback, useEffect, useRef, useState } from "react";

import { microphoneErrorMessage } from "../utils/microphoneError";
import { encodeWav } from "../utils/wav";

const SAMPLE_RATE = 16000;

/** vad-web's own default constraints, so picking a device keeps echo cancellation. */
function getMicStream(deviceId: string | null): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      autoGainControl: true,
      noiseSuppression: true,
      ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
    },
  });
}

/** Armed for the whole call, so the user can barge in at any time. */
export function useMicrophoneVAD(
  onSpeechRealStart: () => void,
  onTurnAudio: (blob: Blob, mimeType: string) => void,
  deviceId: string | null,
) {
  const [micError, setMicError] = useState<string | null>(null);
  const vadRef = useRef<Awaited<ReturnType<typeof MicVAD.new>> | null>(null);
  const initRef = useRef<Promise<void> | null>(null);

  // MicVAD.new() runs once, so its closures read the device through a ref.
  const deviceIdRef = useRef(deviceId);
  deviceIdRef.current = deviceId;

  const ensureVad = useCallback(async () => {
    if (!initRef.current) {
      initRef.current = MicVAD.new({
        baseAssetPath: "/vad/",
        onnxWASMBasePath: "/vad/",
        startOnLoad: false,
        getStream: () => getMicStream(deviceIdRef.current),
        resumeStream: () => getMicStream(deviceIdRef.current),
        // vad-web's 0.3/0.25 gap let room noise keep onSpeechEnd from firing.
        positiveSpeechThreshold: 0.5,
        negativeSpeechThreshold: 0.35,
        // Filters out brief "hmm"s.
        minSpeechMs: 500,
        // The largest piece of reply latency; 700 ms cut users off mid-thought.
        redemptionMs: 1000,
        onSpeechStart: () => console.debug("[VAD] speech start (unconfirmed)"),
        // For barge-in, not onSpeechStart.
        onSpeechRealStart: () => {
          console.debug("[VAD] speech confirmed real");
          onSpeechRealStart();
        },
        onVADMisfire: () => console.debug("[VAD] misfire (too short, ignored)"),
        // Keeps listening, for the next barge-in.
        onSpeechEnd: (audio: Float32Array) => {
          console.debug("[VAD] speech end, samples:", audio.length);
          onTurnAudio(encodeWav(audio, SAMPLE_RATE), "audio/wav");
        },
      })
        .then((vad) => {
          vadRef.current = vad;
        })
        .catch((e: unknown) => {
          setMicError(
            microphoneErrorMessage(e, "Die Spracherkennung konnte nicht gestartet werden."),
          );
        });
    }
    await initRef.current;
  }, [onSpeechRealStart, onTurnAudio]);

  // Warms the ~15MB model during the mic check; the model load is the slow part.
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
