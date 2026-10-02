import { formatRange, halves, type MetricSeries } from "../utils/progressStats";

/**
 * Earlier and recent trainings side by side, each a median widened by its own spread.
 * Nothing is computed between them — no delta, arrow or direction (ADR 0065/0051; ADR
 * 0081's two-stretch construction). Only on a metric's own page, never the overview.
 */
export default function EarlyAndLate({ series }: { series: MetricSeries }) {
  const split = halves(series);
  if (!split) return null;

  return (
    <>
      <h2>Früher und zuletzt</h2>
      <div className="card">
        <div className="early-late">
          <div className="early-late-half">
            <p className="early-late-label">
              Ihre ersten {split.each} Trainings hier
            </p>
            <p className="early-late-range">{formatRange(series, split.early)}</p>
          </div>
          <div className="early-late-half">
            <p className="early-late-label">Ihre letzten {split.each}</p>
            <p className="early-late-range">{formatRange(series, split.late)}</p>
          </div>
        </div>

        {/* The sentence is the feature. Two ranges beside each other are read
            as a before and an after unless something says otherwise, and what
            is missing is not modesty but a basis: nobody has established what a
            good value is here, so nobody can say which of the two is the
            better one. */}
        <p className="muted">
          Zwei Beschreibungen Ihrer eigenen Werte, jede aus {split.each} Trainings. Welcher
          Unterschied zwischen ihnen etwas bedeutet, steht hier nicht, denn dafür gibt es
          für diese Gespräche keinen belegten Richtwert. Szenario und Gesprächspartner
          wechseln außerdem zwischen den Trainings und beeinflussen den Wert mit; mit der
          Auswahl nach Gesprächsanlass auf der Fortschrittsseite lesen Sie beide Spalten
          über dieselbe Art von Gespräch.
        </p>
      </div>
    </>
  );
}
