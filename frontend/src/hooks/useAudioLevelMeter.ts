import { useCallback, useEffect, useRef, useState } from "react";

/** Made together, so a new analyser is never read through the old buffer; reused, so frames allocate nothing. */
function meterSource(analyser: AnalyserNode) {
  return { analyser, samples: new Uint8Array(analyser.fftSize) };
}

type MeterSource = ReturnType<typeof meterSource>;

function readRms({ analyser, samples }: MeterSource): number {
  analyser.getByteTimeDomainData(samples);

  let sumSquares = 0;
  for (const sample of samples) {
    const normalized = (sample - 128) / 128;
    sumSquares += normalized * normalized;
  }

  return Math.sqrt(sumSquares / samples.length);
}

/** The analyser's amplitude per animation frame, as 0..1; `gain` scales the small speech RMS. */
export function useAudioLevelMeter(gain = 1) {
  const [level, setLevel] = useState(0);
  const frameRef = useRef<number | null>(null);
  const sourceRef = useRef<MeterSource | null>(null);

  const stop = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    sourceRef.current = null;
    setLevel(0);
  }, []);

  /** Safe per audio chunk: a running loop is re-pointed, not stacked. */
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

  // The loop re-arms itself every frame.
  useEffect(() => stop, [stop]);

  return { level, start, stop };
}
