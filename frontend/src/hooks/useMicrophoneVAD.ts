import { MicVAD } from "@ricky0123/vad-web";
import { useCallback, useEffect, useRef, useState } from "react";

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
        // vad-web's own defaults (0.3 / 0.25) leave only a 0.05 gap between
        // the positive/negative thresholds — narrower than Silero's own
        // authors recommend (a 0.15 gap, per vad-web's frame-processor
        // typedoc). With that narrow a gap, real-room background noise
        // (headset hiss, faint hum) can keep nudging the speech probability
        // back above negativeSpeechThreshold, so the end-of-speech
        // "redemption" countdown never completes and onSpeechEnd never
        // fires — the mic just never registers the user as done talking.
        // Widening the gap back to Silero's recommended spacing trades a
        // little sensitivity to very quiet speech for reliably detecting
        // end-of-speech in a normal (not dead-silent) room.
        positiveSpeechThreshold: 0.5,
        negativeSpeechThreshold: 0.35,
        // Raised from vad-web's 400ms default to filter out quiet/brief "hmm"s.
        minSpeechMs: 500,
        // How long the silence after a sentence has to last before the turn is
        // sent. vad-web's default is 1400 ms, and it was never chosen here --
        // it is simply what the library does. It is also the single largest
        // piece of the delay between the user finishing and hearing a reply:
        // the whole server pipeline (STT + reply + first audio) was measured at
        // about a second, so the browser was waiting longer than everything
        // else together.
        //
        // 1000 ms is short enough to stop the pause feeling like a hang and
        // long enough to sit out a breath in the middle of a sentence, which is
        // what this guards: cut it too fine and a user who pauses to think has
        // their turn sent half-finished, and the persona answers a fragment.
        // Raised here from 700 for exactly that reason -- someone working out
        // what to say next needs a moment to do it, and being cut off mid-
        // thought is the failure that costs a turn rather than a second.
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
        .catch((e: Error) => {
          setMicError(e.message);
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
