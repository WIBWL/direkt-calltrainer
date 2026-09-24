import { type MetricSeries } from "../utils/progressStats";
import { formatDate } from "../utils/time";

/**
 * A checklist metric across trainings (F-63's opening, see `SeriesShape`): one mark per training with the
 * number of recognised parts, oldest first. No line, since 1, 3, 2, 3 over a band reads as a score climbing to
 * full marks (ADR 0086). Marks are not shaded by count — that would be colour meaning "more is better" (ADR 0065).
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
