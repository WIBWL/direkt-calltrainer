import { formatClock } from "../utils/time";

interface LoudnessCourseProps {
  /** The loudness curve out of `Measurement.detail`: one point per 100 ms,
   * `null` for a silent stretch inside an utterance. */
  values: (number | null)[];
}

/** acoustics.py's `_SAMPLE_INTERVAL_MS` — the curve's only time base. */
const MS_PER_POINT = 100;
/** Moving-average window, 1 s: syllables and word stress average out, a real
 * shift in level survives. */
const SMOOTH_POINTS = 10;
/** How long a departure has to hold (2 s) to be marked. Below that it is
 * delivery, not a change in how the call was conducted. */
const MIN_STRETCH_POINTS = 20;
/** How far outside the call's own spread a stretch has to sit, in multiples of
 * it. Self-referential on purpose — ADR 0051 declined to invent the norms a
 * fixed dB threshold would need. */
const DEVIATION = 2;

/** The longest silence the line is drawn through (2 s); see `polylines`. */
const BRIDGE_POINTS = 20;

const WIDTH = 640;
const PLOT_TOP = 16;
const PLOT_H = 70;
const HEIGHT = PLOT_TOP + PLOT_H;
/** Keeps a marker's caption inside the plot instead of off its edge. */
const LABEL_MARGIN = 70;

type Direction = "louder" | "quieter";

interface Stretch {
  direction: Direction;
  /** Where the departure was largest — what the marker points at. */
  peakIndex: number;
}

const CAPTION: Record<Direction, string> = { louder: "lauter", quieter: "leiser" };

/**
 * The loudness curve across the call (F-37), drawn from what Praat measured
 * (ADR 0047/0051) and stored in `Measurement.detail` (ADR 0029).
 *
 * No figure accompanies it, deliberately: the Measurement's value is a dB span
 * (95th percentile minus 5th) that reads like a level without being one and has
 * no validated norm to be placed against (ADR 0004/0051). The course can be
 * shown without inventing one, against a band drawn from the call's own samples.
 *
 * The horizontal axis is the user's **own speaking time**, not the call clock:
 * backend/session/models.py concatenates their Turns and inserts nothing for
 * the Persona's. Left is early and right is late, but a session timestamp would
 * be a lie — hence the axis label.
 *
 * Inline SVG rather than a charting library: a band, a line and two markers.
 */
export default function LoudnessCourse({ values }: LoudnessCourseProps) {
  const audible = values.filter((value): value is number => value !== null);
  if (audible.length < 2) return null;

  const sorted = [...audible].sort((a, b) => a - b);
  const median = percentile(sorted, 0.5);
  const spread = robustSpread(sorted, median);
  const low = median - DEVIATION * spread;
  const high = median + DEVIATION * spread;

  const floor = sorted.reduce((least, value) => Math.min(least, value), Infinity);
  const ceiling = sorted.reduce((most, value) => Math.max(most, value), -Infinity);
  const span = ceiling - floor || 1;

  const x = (index: number) => (index / (values.length - 1)) * WIDTH;
  const y = (value: number) => PLOT_TOP + PLOT_H - ((value - floor) / span) * PLOT_H;

  const smoothed = smooth(values);
  const stretches = findStretches(smoothed, low, high);
  const total = formatClock((values.length * MS_PER_POINT) / 1000);

  return (
    <figure className="loudness-course">
      <svg
        className="loudness-course-plot"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={describe(stretches, total)}
      >
        {/* Clamped: on an even call the band is wider than the curve's own
            range, and the SVG does not clip its overflow. */}
        <rect
          className="loudness-course-band"
          x={0}
          y={Math.max(PLOT_TOP, y(high))}
          width={WIDTH}
          height={Math.max(
            1,
            Math.min(PLOT_TOP + PLOT_H, y(low)) - Math.max(PLOT_TOP, y(high)),
          )}
        />
        <line className="loudness-course-median" x1={0} y1={y(median)} x2={WIDTH} y2={y(median)} />
        {polylines(smoothed, x, y).map((points, i) => (
          <polyline className="loudness-course-line" key={i} points={points} />
        ))}
        {stretches.map((stretch) => (
          <Marker key={stretch.direction} stretch={stretch} smoothed={smoothed} x={x} y={y} />
        ))}
      </svg>

      <div className="loudness-course-axis">
        <span>0:00</span>
        <span className="loudness-course-axis-name">Ihre Sprechzeit</span>
        <span>{total}</span>
      </div>

      <figcaption className="loudness-course-legend">
        Das Band ist der Bereich, in dem Sie die meiste Zeit gesprochen haben; markiert
        ist, wo Sie ihn mindestens zwei Sekunden lang verlassen haben. Gezählt wird nur
        Ihre eigene Sprechzeit, nicht die Dauer des Gesprächs.
      </figcaption>
    </figure>
  );
}

/** One departure, at its largest point. The caption sits above a louder stretch
 * and below a quieter one so it never crosses its own line, and turns in at the
 * edges rather than running off the plot. */
function Marker({
  stretch,
  smoothed,
  x,
  y,
}: {
  stretch: Stretch;
  smoothed: (number | null)[];
  x: (index: number) => number;
  y: (value: number) => number;
}) {
  const value = smoothed[stretch.peakIndex];
  if (value === null || value === undefined) return null;

  const at = x(stretch.peakIndex);
  const anchor = at < LABEL_MARGIN ? "start" : at > WIDTH - LABEL_MARGIN ? "end" : "middle";
  const above = stretch.direction === "louder";

  return (
    <g className="loudness-course-marker">
      <circle cx={at} cy={y(value)} r={2.6} />
      <text x={at} y={above ? y(value) - 8 : y(value) + 14} textAnchor={anchor}>
        {CAPTION[stretch.direction]} · {formatClock((stretch.peakIndex * MS_PER_POINT) / 1000)}
      </text>
    </g>
  );
}

/** What the picture says, for a reader who cannot see it. */
function describe(stretches: Stretch[], total: string): string {
  const opening = `Lautstärkeverlauf über ${total} Sprechzeit`;
  if (stretches.length === 0) {
    return `${opening}: durchgehend im gewohnten Bereich, ohne längere Abweichung.`;
  }
  const parts = stretches.map((stretch) => CAPTION[stretch.direction]);
  return `${opening}: ${parts.join(" an einer Stelle, ")} an einer Stelle.`;
}

/**
 * The width the band is built from. Kept in step with `_band` in
 * backend/feedback/metrics.py, which the wrap-up is written from — the two
 * disagreeing would put a sentence about a quieter stretch above a chart that
 * marks none.
 *
 * Median absolute deviation, not a percentile band: a stretch covering a third
 * of the call *is* the tenth percentile, so a percentile band goes blind to the
 * long shifts that matter most. Zero falls back to the mean deviation, which
 * vanishes only for a constant curve.
 */
function robustSpread(sorted: number[], median: number): number {
  const deviations = sorted.map((value) => Math.abs(value - median)).sort((a, b) => a - b);
  const middle = percentile(deviations, 0.5);
  if (middle > 0) return middle;
  return deviations.reduce((sum, value) => sum + value, 0) / (deviations.length || 1);
}

/** Linear-interpolated percentile of an already sorted series. */
function percentile(sorted: number[], fraction: number): number {
  const at = (sorted.length - 1) * fraction;
  const below = sorted[Math.floor(at)] ?? 0;
  const above = sorted[Math.ceil(at)] ?? below;
  return below + (above - below) * (at - Math.floor(at));
}

/** The curve with the jitter taken out. A window more than half silent yields
 * no value — its average would be the edge of the silence, not a spoken level. */
function smooth(values: (number | null)[]): (number | null)[] {
  const half = Math.floor(SMOOTH_POINTS / 2);
  return values.map((_, index) => {
    let sum = 0;
    let count = 0;
    for (let i = Math.max(0, index - half); i <= Math.min(values.length - 1, index + half); i++) {
      const value = values[i];
      if (value !== null && value !== undefined) {
        sum += value;
        count += 1;
      }
    }
    return count >= half ? sum / count : null;
  });
}

/**
 * At most one stretch per direction, the one that departed furthest over its
 * length: one marker each reads as "here it moved" rather than as a scatter of
 * every wobble.
 *
 * A call held evenly yields none — the band comes from its own samples, so a
 * steady speaker never leaves it. A flat call must not be given a variation.
 */
function findStretches(smoothed: (number | null)[], low: number, high: number): Stretch[] {
  const marked: (Direction | null)[] = smoothed.map((value) => {
    if (value === null) return null;
    if (value > high) return "louder";
    if (value < low) return "quieter";
    return null;
  });

  const best: Partial<Record<Direction, { deviation: number; peakIndex: number }>> = {};
  let index = 0;
  while (index < marked.length) {
    const direction = marked[index];
    if (!direction) {
      index += 1;
      continue;
    }
    let end = index;
    while (end < marked.length && marked[end] === direction) end += 1;

    if (end - index >= MIN_STRETCH_POINTS) {
      let deviation = 0;
      let peak = 0;
      let peakIndex = index;
      for (let i = index; i < end; i++) {
        const value = smoothed[i];
        if (value === null || value === undefined) continue;
        const distance = direction === "louder" ? value - high : low - value;
        deviation += distance;
        if (distance > peak) {
          peak = distance;
          peakIndex = i;
        }
      }
      const current = best[direction];
      if (!current || deviation > current.deviation) best[direction] = { deviation, peakIndex };
    }
    index = end;
  }

  return (["louder", "quieter"] as const).flatMap((direction) => {
    const found = best[direction];
    return found ? [{ direction, peakIndex: found.peakIndex }] : [];
  });
}

/**
 * The line, drawn across the breathing pauses but not across the silences.
 *
 * Gaps up to `BRIDGE_POINTS` are joined through: those are pauses inside an
 * utterance, and breaking at every one shattered the course into fragments. A
 * longer silence still ends the line — nothing was measured there, and a segment
 * across it would assert a level nobody spoke at.
 */
function polylines(
  series: (number | null)[],
  x: (index: number) => number,
  y: (value: number) => number,
): string[] {
  const out: string[] = [];
  let run: string[] = [];
  let gap = 0;

  series.forEach((value, index) => {
    if (value === null) {
      gap += 1;
      return;
    }
    if (gap > BRIDGE_POINTS) {
      if (run.length > 1) out.push(run.join(" "));
      run = [];
    }
    gap = 0;
    run.push(`${x(index).toFixed(1)},${y(value).toFixed(1)}`);
  });

  if (run.length > 1) out.push(run.join(" "));
  return out;
}
