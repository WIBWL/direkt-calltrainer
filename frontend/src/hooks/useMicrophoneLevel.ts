import { useCallback, useEffect, useRef, useState } from "react";

import { microphoneErrorMessage } from "../utils/microphoneError";
import { useAudioLevelMeter } from "./useAudioLevelMeter";

/** The mic check's meter, independent of the call's VAD. `start()` reads the current `deviceId`. */
export function useMicrophoneLevel(deviceId: string | null) {
  const [error, setError] = useState<string | null>(null);

  const { level, start: startMeter, stop: stopMeter } = useAudioLevelMeter();
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const attemptRef = useRef(0);

  const stop = useCallback(() => {
    // Also retires an attempt still in the permission prompt.
    attemptRef.current += 1;
    stopMeter();

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

  }, [stopMeter]);

  /** Reports success; `null` when a newer `start()` superseded it. */
  const start = useCallback(async (): Promise<boolean | null> => {
    stop(); // a retry must not leave the previous stream open
    setError(null);
    // A newer attempt may start during the prompt; this one then closes its own stream.
    const attempt = ++attemptRef.current;
    const superseded = () => attempt !== attemptRef.current;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      });
      if (superseded()) {
        stream.getTracks().forEach((track) => track.stop());
        return null;
      }
      streamRef.current = stream;

      const ctx = new AudioContext();
      audioContextRef.current = ctx;

      if (ctx.state === "suspended") {
        await ctx.resume();
      }
      if (superseded()) return null;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);

      startMeter(analyser);
      return true;
    } catch (e) {
      if (superseded()) return null; // the newer attempt owns the state now
      stop(); // the failure may have come after getUserMedia handed over a live stream
      setError(microphoneErrorMessage(e));
      return false;
    }
  }, [deviceId, startMeter, stop]);

  useEffect(() => stop, [stop]);

  return { level, error, start, stop };
}
