import { formatRange, halves, type MetricSeries } from "../utils/progressStats";

/** Earlier and recent trainings side by side, nothing computed between them (ADR 0051/0065). */
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

        {/* The sentence is the feature: two ranges read as before and after unless told otherwise. */}
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
