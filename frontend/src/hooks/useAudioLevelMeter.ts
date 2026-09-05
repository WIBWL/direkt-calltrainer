import { useCallback, useEffect, useRef, useState } from "react";

/** What is being metered, plus a scratch buffer sized for it. The two are made
 * together so a new analyser can never be read through the previous one's
 * buffer, and the buffer is reused so the frame loop allocates nothing.
 * The sample type is inferred rather than written out: which `Uint8Array` the
 * DOM's `getByteTimeDomainData` accepts differs between TypeScript versions. */
function meterSource(analyser: AnalyserNode) {
  return { analyser, samples: new Uint8Array(analyser.fftSize) };
}

type MeterSource = ReturnType<typeof meterSource>;

/** RMS amplitude (0..1) of the analyser's current time-domain window. */
function readRms({ analyser, samples }: MeterSource): number {
  analyser.getByteTimeDomainData(samples);

  let sumSquares = 0;
  for (const sample of samples) {
    const normalized = (sample - 128) / 128;
    sumSquares += normalized * normalized;
  }

  return Math.sqrt(sumSquares / samples.length);
}

/**
 * Samples an AnalyserNode once per animation frame and exposes its amplitude
 * as a normalized 0..1 `level`.
 *
 * Shared by the two places that meter audio — the pre-call microphone check
 * (input) and persona playback (output) — because the measurement is the same
 * in both; only what is metered and how far the value is scaled differ.
 * `gain` covers the latter: speech RMS is naturally small, so a meter that
 * should visibly react needs the raw value scaled before it is clamped.
 */
export function useAudioLevelMeter(gain = 1) {
  const [level, setLevel] = useState(0);
  const frameRef = useRef<number | null>(null);
  const sourceRef = useRef<MeterSource | null>(null);

  /** Ends the loop and drops the level back to silence. */
  const stop = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    sourceRef.current = null;
    setLevel(0);
  }, []);

  /** Arms the meter on `analyser`. Safe to call per audio chunk: a loop that
   * is already running is not stacked, it is re-pointed — so handing over a
   * *different* analyser meters that one, rather than being ignored. */
  const start = useCallback(
    (analyser: AnalyserNode) => {
      if (sourceRef.current?.analyser !== analyser) {
        sourceRef.current = meterSource(analyser);
      }
      if (frameRef.current !== null) return;

      const tick = () => {
        const source = sourceRef.current;
        if (source === null) return; // stopped between frames
        setLevel(Math.min(1, readRms(source) * gain));
        frameRef.current = requestAnimationFrame(tick);
      };

      frameRef.current = requestAnimationFrame(tick);
    },
    [gain],
  );

  // The loop outlives the component otherwise — it re-arms itself every frame.
  useEffect(() => stop, [stop]);

  return { level, start, stop };
}
