import { useCallback, useEffect, useRef, useState } from "react";

import { useAudioLevelMeter } from "./useAudioLevelMeter";

/** Converts browser microphone errors into stable German user-facing messages.
 * Browser-provided error text is intentionally not exposed because it differs
 * between browsers and may not match the application's language. */
function microphoneErrorMessage(error: unknown): string {
  if (!(error instanceof DOMException)) {
    return "Das Mikrofon konnte nicht geöffnet werden.";
  }

  switch (error.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Der Mikrofonzugriff wurde blockiert.";

    case "NotFoundError":
      return "Es wurde kein verfügbares Mikrofon gefunden.";

    case "NotReadableError":
      return "Das Mikrofon kann derzeit nicht verwendet werden. Möglicherweise wird es von einer anderen Anwendung verwendet.";

    case "OverconstrainedError":
      return "Das ausgewählte Mikrofon ist nicht mehr verfügbar.";

    case "AbortError":
      return "Der Mikrofonzugriff wurde unterbrochen. Starten Sie den Test erneut.";

    default:
      return "Das Mikrofon konnte nicht geöffnet werden.";
  }
}

/**
 * Measures the input level of the active microphone independently of the
 * conversation VAD used during a real training session. The metering itself
 * is shared with persona playback (see useAudioLevelMeter); what this hook
 * owns is the capture stream behind it.
 *
 * `deviceId` selects which input to open — `null` leaves it to the browser's
 * own default. Re-created every render, so `start()` always reads the current
 * value; MicCheck restarts the test when it changes while running.
 */
export function useMicrophoneLevel(deviceId: string | null) {
  const [error, setError] = useState<string | null>(null);

  const { level, start: startMeter, stop: stopMeter } = useAudioLevelMeter();
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const stop = useCallback(() => {
    stopMeter();

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

    // The last device label stays visible after the completed test.
  }, [stopMeter]);

  /** Opens the microphone and starts metering it. Reports whether that worked,
   * so the caller can show the failure as a state of its own instead of
   * waiting for a level that is never going to arrive. */
  const start = useCallback(async (): Promise<boolean> => {
    stop(); // a retry must not leave the previous stream open
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      });
      streamRef.current = stream;

      const ctx = new AudioContext();
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);

      startMeter(analyser);
      return true;
    } catch (e) {
      stop(); // the failure may have come after getUserMedia handed over a live stream
      setError(microphoneErrorMessage(e));
      return false;
    }
  }, [deviceId, startMeter, stop]);

  useEffect(() => stop, [stop]);

  return { level, error, start, stop };
}
