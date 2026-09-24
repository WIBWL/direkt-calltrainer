import { useCallback, useEffect, useRef, useState } from "react";

import { microphoneErrorMessage } from "../utils/microphoneError";
import { useAudioLevelMeter } from "./useAudioLevelMeter";

/**
 * Meters the microphone for the mic check, independent of the call's VAD; owns
 * the capture stream, the metering is `useAudioLevelMeter`. `deviceId` null
 * means the browser default; `start()` always reads the current value.
 */
export function useMicrophoneLevel(deviceId: string | null) {
  const [error, setError] = useState<string | null>(null);

  const { level, start: startMeter, stop: stopMeter } = useAudioLevelMeter();
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const attemptRef = useRef(0);

  const stop = useCallback(() => {
    // Also retires an attempt still waiting on getUserMedia, so a cancel or an
    // unmount during the permission prompt closes that stream on arrival.
    attemptRef.current += 1;
    stopMeter();

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

    // The last device label stays visible after the completed test.
  }, [stopMeter]);

  /** Opens the microphone and starts metering it. Reports whether that worked,
   * so the caller can show the failure as a state of its own instead of
   * waiting for a level that is never going to arrive — or `null` when a newer
   * call to `start()` superseded this one, which is neither: that call's own
   * answer is the one to act on. */
  const start = useCallback(async (): Promise<boolean | null> => {
    stop(); // a retry must not leave the previous stream open
    setError(null);
    // A device change can start a second attempt while the first is still
    // waiting on getUserMedia (the permission prompt, typically). `stop()`
    // above finds nothing to close then, so the older attempt has to notice
    // on arrival that it was superseded and close its own stream — otherwise
    // it lands in no ref and the microphone stays on.
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
      // The newer attempt's stop() has already closed this stream and context.
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
