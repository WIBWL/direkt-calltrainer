import { completeParts, partsTotal, type MetricSeries } from "../utils/progressStats";
import { formatDate } from "../utils/time";

/**
 * A checklist metric across the trainings: how many parts were recognised in
 * each, one mark per training, oldest first (F-63's opening, see
 * `SeriesShape`).
 *
 * In place of a line, and for one reason. A line through 1, 3, 2, 3 over a band
 * reads as a score climbing towards full marks, and the single call's tile
 * already refused that reading by showing the parts rather than "1 von 3"
 * (ADR 0086). A row of counts says the same thing without drawing a direction
 * through it.
 *
 * Every mark looks alike whatever it holds. Shading them by count would be a
 * colour meaning "more is better", which ADR 0065 keeps off this screen; the
 * number printed in the mark is the whole of the reading.
 */
export default function PartsStrip({ series }: { series: MetricSeries }) {
  // One image with the numbers in its name, the way the Sparkline is: a list of
  // bare digits would be read out as a list of entries and their values, with
  // nothing to say what they count.
  return (
    <span
      className="parts-strip"
      role="img"
      aria-label={`${series.name}, erkannte Teile je Training, ältestes zuerst: ${series.points
        .map((p) => Math.round(p.value))
        .join(", ")}.`}
    >
      {series.points.map((point) => (
        <span
          key={point.sessionId}
          className="parts-chip"
          // For the mouse only; the strip's own name carries the numbers.
          title={`${formatDate(point.at) ?? point.at} · ${point.scenario}`}
        >
          {Math.round(point.value)}
        </span>
      ))}
    </span>
  );
}

/**
 * The sentence that goes with the strip: in how many trainings every part was
 * recognised, out of how many. Null where the unit does not say how many parts
 * there are, rather than a sentence with a guessed number in it.
 */
export function partsSummary(series: MetricSeries): string | null {
  const total = partsTotal(series);
  const complete = completeParts(series);
  if (total === null || complete === null) return null;
  return `In ${complete} von ${series.points.length} Trainings alle ${total} Teile erkannt`;
}
