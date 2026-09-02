import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Measures the input level of the active microphone independently of the
 * conversation VAD used during a real training session.
 */
export function useMicrophoneLevel() {
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Browsers expose the device label only after microphone permission was granted.
  const [deviceLabel, setDeviceLabel] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const poll = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);

    let sumSquares = 0;

    for (const sample of data) {
      const normalized = (sample - 128) / 128;
      sumSquares += normalized * normalized;
    }

    setLevel(Math.sqrt(sumSquares / data.length));
    rafRef.current = requestAnimationFrame(poll);
  }, []);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const [audioTrack] = stream.getAudioTracks();
      setDeviceLabel(audioTrack?.label || null);

      const ctx = new AudioContext();
      audioContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      analyserRef.current = analyser;

      poll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [poll]);

  const stop = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;
    analyserRef.current = null;

    // Keep the last device label visible after the completed test.
    setLevel(0);
  }, []);

  useEffect(() => stop, [stop]);

  return { level, error, deviceLabel, start, stop };
}