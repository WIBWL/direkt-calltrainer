import {
  analyseLoudness,
  describeLoudness,
  loudnessClock,
  loudnessRuns,
  LOUDNESS_CAPTION,
  type LoudnessCurve,
  type LoudnessStretch,
} from "../utils/loudness";

interface LoudnessCourseProps {
  /** The loudness curve out of `Measurement.detail`: one point per 100 ms,
   * `null` for a silent stretch inside an utterance. */
  values: (number | null)[];
}

const WIDTH = 640;
const PLOT_TOP = 16;
const PLOT_H = 70;
const HEIGHT = PLOT_TOP + PLOT_H;
/** Keeps a marker's caption inside the plot instead of off its edge. */
const LABEL_MARGIN = 70;

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
 * The arithmetic behind all four lives in `utils/loudness.ts`, because the
 * downloadable report draws the same course and must draw the same one.
 */
export default function LoudnessCourse({ values }: LoudnessCourseProps) {
  const curve = analyseLoudness(values);
  if (!curve) return null;

  const x = (index: number) => (index / (curve.points - 1)) * WIDTH;
  const y = (value: number) => PLOT_TOP + PLOT_H - ((value - curve.floor) / curve.span) * PLOT_H;

  return (
    <figure className="loudness-course">
      <svg
        className="loudness-course-plot"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={describeLoudness(curve)}
      >
        {/* Clamped: on an even call the band is wider than the curve's own
            range, and the SVG does not clip its overflow. */}
        <rect
          className="loudness-course-band"
          x={0}
          y={Math.max(PLOT_TOP, y(curve.high))}
          width={WIDTH}
          height={Math.max(
            1,
            Math.min(PLOT_TOP + PLOT_H, y(curve.low)) - Math.max(PLOT_TOP, y(curve.high)),
          )}
        />
        <line
          className="loudness-course-median"
          x1={0}
          y1={y(curve.median)}
          x2={WIDTH}
          y2={y(curve.median)}
        />
        {loudnessRuns(curve.smoothed).map((run, i) => (
          <polyline
            className="loudness-course-line"
            key={i}
            points={run
              .map((index) => `${x(index).toFixed(1)},${y(curve.smoothed[index]!).toFixed(1)}`)
              .join(" ")}
          />
        ))}
        {curve.stretches.map((stretch) => (
          <Marker key={stretch.direction} stretch={stretch} curve={curve} x={x} y={y} />
        ))}
      </svg>

      <div className="loudness-course-axis">
        <span>0:00</span>
        <span className="loudness-course-axis-name">Ihre Sprechzeit</span>
        <span>{curve.total}</span>
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
  curve,
  x,
  y,
}: {
  stretch: LoudnessStretch;
  curve: LoudnessCurve;
  x: (index: number) => number;
  y: (value: number) => number;
}) {
  const value = curve.smoothed[stretch.peakIndex];
  if (value === null || value === undefined) return null;

  const at = x(stretch.peakIndex);
  const anchor = at < LABEL_MARGIN ? "start" : at > WIDTH - LABEL_MARGIN ? "end" : "middle";
  const above = stretch.direction === "louder";

  return (
    <g className="loudness-course-marker">
      <circle cx={at} cy={y(value)} r={2.6} />
      <text x={at} y={above ? y(value) - 8 : y(value) + 14} textAnchor={anchor}>
        {LOUDNESS_CAPTION[stretch.direction]} · {loudnessClock(stretch.peakIndex)}
      </text>
    </g>
  );
}
