interface SparklineProps {
  /** A curve from Messung.detail_json, sampled at a fixed rate; null marks a
   * stretch with no value (silence, for loudness). */
  values: (number | null)[];
  label: string;
}

const WIDTH = 160;
const HEIGHT = 28;

/**
 * The course of one metric across the whole call, drawn from the curve Praat
 * measured (ADR 0044/0048) and stored in Messung.detail_json (ADR 0029).
 *
 * Inline SVG rather than a charting library: it is one polyline, and the app
 * has no chart dependency to justify for it. Gaps are breaks in the line, not
 * interpolated across — a silent stretch is missing data, not a low value.
 */
export default function Sparkline({ values, label }: SparklineProps) {
  const present = values.filter((v): v is number => v !== null);
  if (present.length < 2) return null;

  const min = Math.min(...present);
  const max = Math.max(...present);
  const span = max - min || 1;
  const x = (i: number) => (i / (values.length - 1)) * WIDTH;
  const y = (v: number) => HEIGHT - ((v - min) / span) * HEIGHT;

  // One <polyline> per uninterrupted run, so gaps stay gaps.
  const runs: string[] = [];
  let run: string[] = [];
  values.forEach((value, i) => {
    if (value === null) {
      if (run.length > 1) runs.push(run.join(" "));
      run = [];
    } else {
      run.push(`${x(i).toFixed(1)},${y(value).toFixed(1)}`);
    }
  });
  if (run.length > 1) runs.push(run.join(" "));

  return (
    <svg
      className="sparkline"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width={WIDTH}
      height={HEIGHT}
      role="img"
      aria-label={label}
    >
      {runs.map((points, i) => (
        <polyline key={i} points={points} fill="none" strokeWidth={1.5} />
      ))}
    </svg>
  );
}
