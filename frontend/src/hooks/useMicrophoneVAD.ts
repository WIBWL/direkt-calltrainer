import { MicVAD } from "@ricky0123/vad-web";
import { useCallback, useEffect, useRef, useState } from "react";

import { microphoneErrorMessage } from "../utils/microphoneError";
import { encodeWav } from "../utils/wav";

const SAMPLE_RATE = 16000;

/** Mirrors vad-web's own default constraints (real-time-vad.js's
 * getStream/resumeStream) so picking a device doesn't also drop echo
 * cancellation etc. for the whole call. */
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

/**
 * Arms the microphone for the whole call — including while the Persona is
 * "thinking"/"speaking" — so the user can barge in at any time.
 */
export function useMicrophoneVAD(
  onSpeechRealStart: () => void,
  onTurnAudio: (blob: Blob, mimeType: string) => void,
  deviceId: string | null,
) {
  const [micError, setMicError] = useState<string | null>(null);
  const vadRef = useRef<Awaited<ReturnType<typeof MicVAD.new>> | null>(null);
  const initRef = useRef<Promise<void> | null>(null);

  // MicVAD.new() below runs once, ever (see initRef), so its getStream/
  // resumeStream closures capture whatever deviceId was current at that
  // point -- reading it from a ref instead means a later selection still
  // takes effect on the next pause()/start() cycle (e.g. the mute toggle).
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
        // vad-web's defaults (0.3 / 0.25) leave a 0.05 gap, narrower than
        // Silero's recommended 0.15: room noise then keeps the probability
        // above the negative threshold, so onSpeechEnd never fires and the
        // turn is never sent. The wider gap costs a little quiet-speech
        // sensitivity.
        positiveSpeechThreshold: 0.5,
        negativeSpeechThreshold: 0.35,
        // Raised from vad-web's 400ms default to filter out quiet/brief "hmm"s.
        minSpeechMs: 500,
        // Silence before the turn is sent; the largest piece of reply latency
        // (vad-web's 1400 ms outlasted the whole server pipeline). Do not go
        // much lower: 700 ms cut users off mid-thought, sending half a turn
        // that the persona then answers — a lost turn, not a lost second.
        redemptionMs: 1000,
        onSpeechStart: () => console.debug("[VAD] speech start (unconfirmed)"),
        // Fires once sustained past minSpeechMs -- use this for barge-in, not onSpeechStart above.
        onSpeechRealStart: () => {
          console.debug("[VAD] speech confirmed real");
          onSpeechRealStart();
        },
        onVADMisfire: () => console.debug("[VAD] misfire (too short, ignored)"),
        // No pause() here — keeps listening so the user can barge in again right away.
        onSpeechEnd: (audio: Float32Array) => {
          console.debug("[VAD] speech end, samples:", audio.length);
          onTurnAudio(encodeWav(audio, SAMPLE_RATE), "audio/wav");
        },
      })
        .then((vad) => {
          vadRef.current = vad;
        })
        .catch((e: unknown) => {
          // A refused microphone reads as it does on the microphone check;
          // anything else here is the voice detection failing to start.
          setMicError(
            microphoneErrorMessage(e, "Die Spracherkennung konnte nicht gestartet werden."),
          );
        });
    }
    await initRef.current;
  }, [onSpeechRealStart, onTurnAudio]);

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
