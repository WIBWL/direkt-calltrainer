import { useCallback, useEffect, useRef, useState } from "react";

import { useAudioLevelMeter } from "./useAudioLevelMeter";

/**
 * Measures the input level of the active microphone independently of the
 * conversation VAD used during a real training session. The metering itself
 * is shared with persona playback (see useAudioLevelMeter); what this hook
 * owns is the capture stream behind it.
 */
export function useMicrophoneLevel() {
  const [error, setError] = useState<string | null>(null);

  // Browsers expose the device label only after microphone permission was granted.
  const [deviceLabel, setDeviceLabel] = useState<string | null>(null);

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
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const [audioTrack] = stream.getAudioTracks();
      setDeviceLabel(audioTrack?.label || null);

      const ctx = new AudioContext();
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);

      startMeter(analyser);
      return true;
    } catch (e) {
      stop(); // the failure may have come after getUserMedia handed over a live stream
      setError(e instanceof Error ? e.message : String(e));
      return false;
    }
  }, [startMeter, stop]);

  useEffect(() => stop, [stop]);

  return { level, error, deviceLabel, start, stop };
}
