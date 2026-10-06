import { type MetricSeries } from "../utils/progressStats";
import { formatDate } from "../utils/time";

/** A checklist across trainings: marks, not a line (ADR 0086), and not shaded by count (ADR 0065). */
export default function PartsStrip({ series }: { series: MetricSeries }) {
  // One image named with the numbers, like the Sparkline.
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
          title={`${formatDate(point.at) ?? point.at} · ${point.scenario}`}
        >
          {Math.round(point.value)}
        </span>
      ))}
    </span>
  );
}
