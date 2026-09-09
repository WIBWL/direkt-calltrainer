import type { MetricSeries } from "../utils/progressStats";
import { formatValue } from "../utils/progressStats";

/**
 * One Kennzahl over the trainings in the period (F-13,
 * docs/dashboard-konzept.md).
 *
 * What it draws and what it deliberately does not: the user's own values as
 * points on a plain line, and behind them the band they usually fall in, which
 * is their own median widened by their own spread. No target band, no colour
 * that means good or bad, no arrow, no regression line. A trend line through
 * nine points from nine different Scenarios would assert a direction that the
 * data cannot carry, and ADR 0065 rules exactly that out for this view.
 *
 * Inline SVG, like LoudnessCourse: a band, a line and a few dots do not need a
 * charting library, and the alternative would ship one for this.
 *
 * The accessible name carries the numbers, so the chart is not the only place
 * the information exists. The detail view repeats them as a real table.
 */
export default function Sparkline({
  series,
  width = 240,
  height = 56,
  showDots = true,
}: {
  series: MetricSeries;
  width?: number;
  height?: number;
  showDots?: boolean;
}) {
  const values = series.points.map((p) => p.value);
  if (values.length === 0) return null;

  const lowest = Math.min(...values, series.band?.low ?? Infinity);
  const highest = Math.max(...values, series.band?.high ?? -Infinity);
  // A flat series would divide by zero; giving it a nominal span puts the line
  // in the middle of the box instead, which is what a flat series looks like.
  const span = highest - lowest || Math.abs(highest) || 1;
  const pad = 6;
  const plot = height - pad * 2;

  const x = (index: number) =>
    values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
  const y = (value: number) => pad + plot - ((value - lowest) / span) * plot;

  const line = series.points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");

  return (
    <svg
      className="sparkline"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={describe(series)}
    >
      {series.band && (
        <rect
          className="sparkline-band"
          x={0}
          y={Math.max(0, y(series.band.high))}
          width={width}
          height={Math.max(1, Math.min(height, y(series.band.low)) - Math.max(0, y(series.band.high)))}
        />
      )}

      {values.length > 1 && <polyline className="sparkline-line" points={line} />}

      {showDots &&
        series.points.map((point, index) => (
          <circle
            className="sparkline-dot"
            key={point.sessionId}
            cx={x(index)}
            cy={y(point.value)}
            r={values.length > 20 ? 1.8 : 2.6}
          />
        ))}
    </svg>
  );
}

/** The chart in words: how many trainings, the range they covered, and the
 *  most recent value. Stated, never judged. */
function describe(series: MetricSeries): string {
  const values = series.points.map((p) => p.value);
  const last = values[values.length - 1] ?? 0;
  const lowest = formatValue(Math.min(...values), series.unit);
  const highest = formatValue(Math.max(...values), series.unit);
  return (
    `${series.name}: ${values.length} Trainings, Werte von ${lowest} bis ${highest}, ` +
    `zuletzt ${formatValue(last, series.unit)}.`
  );
}
