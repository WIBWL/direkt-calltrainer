import { formatRange, halves, type MetricSeries } from "../utils/progressStats";

/**
 * The user's earlier trainings and their recent ones, described side by side.
 *
 * The page's answer to the question the dashboard has never answered — "has
 * anything changed?" — given under the constraint that it may not answer it.
 * ADR 0065 rules out a delta, an arrow and any word for a direction, and
 * ADR 0051 rules out the norm that would be needed to say whether a change was
 * an improvement. What is left, and what this is, is the construction ADR 0081
 * already uses for the two stretches of a single call: put two descriptions
 * beside each other, compute nothing between them, and say so.
 *
 * Nothing here is derived from the pair. Each column is a median widened by its
 * own half's spread, exactly as the overall band is, and the two are laid out
 * side by side rather than one above the other precisely so that neither reads
 * as coming after the other in an argument.
 *
 * Deliberately on the metric's own page and not on the overview. A reader on
 * this page has asked about one figure; sixteen of these on the overview would
 * be sixteen invitations to read a direction into a pair of ranges, which is
 * how a comparison becomes a score without anybody deciding to build one.
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
