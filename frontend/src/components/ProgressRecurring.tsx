import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useProgressContext } from "../ProgressContext";
import type { FocusGoal, SessionSummary } from "../protocol";
import { progressGoalPath } from "../routes";
import { MIN_MENTIONS, mentionSummary, type GoalMentions } from "../utils/goalMentions";
import InfoDetails from "./InfoDetails";
import MentionTally from "./MentionTally";
import SectionHeading from "./SectionHeading";

/**
 * Block D: what the wrap-ups keep coming back to, counted from each point's focus goal. A frequency of
 * statements, not a measurement (ADR 0004, ADR 0065): "genannt", over a named denominator, never a percentage.
 * The practice suggestion (block E) is handed in and drawn as a full-width band under the lists.
 */
export default function ProgressRecurring({
  sessions,
  catalogue,
  practice,
}: {
  sessions: SessionSummary[];
  /** The focus catalogue, for turning a key into its German title. Served with
   *  the selection (`GET /api/focus`), so the wording lives in one place. */
  catalogue: FocusGoal[];
  /** The suggestion card, shown beside the two lists. Only where there is
   *  something recurring: with nothing named twice it has no ground to stand
   *  on, and `ProgressPractice` would render nothing anyway. */
  practice?: ReactNode;
}) {
  const { strengths, improvements, total } = mentionSummary(sessions);
  const titles = new Map(catalogue.map((goal) => [goal.key, goal.title]));
  const nothing = strengths.length === 0 && improvements.length === 0;

  return (
    <section className="progress-section" aria-labelledby="recurring-title">
      <SectionHeading
        id="recurring-title"
        title="Was in Ihren Auswertungen wiederkehrt"
      />

      {nothing ? (
        <div className="card">
          <p className="progress-preview-note">{emptyText(total)}</p>
        </div>
      ) : (
        <>
          {/* One card each, side by side. The two lists answer different
              questions and were previously two columns inside one border, where
              the eye read them as one table with a gap in the middle. */}
          <div className="recurring-columns">
            <Column
              heading="Häufig als Stärke genannt"
              entries={strengths}
              titles={titles}
              total={total}
              empty="Bisher wurde keine Stärke mehrfach genannt."
            />
            <Column
              heading="Häufig als Verbesserung genannt"
              entries={improvements}
              titles={titles}
              total={total}
              empty="Bisher wurde kein Verbesserungspunkt mehrfach genannt."
            />
          </div>

          {/* Full width, directly under the lists: it follows from what they say, and as a third column it ran
              three times their height. */}
          {practice}

          {/* A footnote to the whole section, naming both lists: directly under the suggestion, "gezählt wird"
              would read as about the suggestion. The written-not-measured sentence stays in view; the rules of
              the count go behind the "i". */}
          <p className="progress-preview-note recurring-note">
            In den beiden Listen oben ist gezählt, was Ihre Auswertungen geschrieben haben,
            nicht was gemessen wurde.
          </p>
          <InfoDetails label="Wie gezählt wird">
            <p>
              Gezählt wird, in wie vielen Ihrer {total} ausgewerteten Trainings ein Thema genannt
              wurde, nicht wie oft es in einem Training vorkam. Das ist eine Häufigkeit von
              Aussagen und keine Messung: Es steht hier, weil die Auswertungen es geschrieben
              haben, nicht weil etwas nachgemessen wurde.
            </p>
            <p>
              Aufgenommen wird ein Thema ab {MIN_MENTIONS} Nennungen, denn ein einzelner Punkt
              aus einem einzelnen Gespräch ist eine Beobachtung und kein Muster. Trainings ohne
              Auswertung, und Auswertungen von vor der Einführung dieser Zuordnung, zählen nicht
              mit.
            </p>
          </InfoDetails>
        </>
      )}
    </section>
  );
}

/**
 * The empty-block text. Distinguishes nothing analysed from nothing said twice; wrap-ups predating the goal
 * tags are indistinguishable in the data, so they are folded into the first sentence rather than claimed.
 */
function emptyText(total: number): string {
  if (total === 0) {
    return (
      "Hier steht später, was Ihre Auswertungen wiederholt nennen. Bisher liegt dafür keine " +
      "ausgewertete Aufzeichnung vor. Auswertungen, die vor der Einführung dieser Zuordnung " +
      "geschrieben wurden, zählen nicht mit, weil ihnen die Zuordnung fehlt."
    );
  }
  return (
    `In Ihren ${total} ausgewerteten Trainings wurde bisher kein Thema mehrfach genannt. ` +
    `Sobald dasselbe Thema in ${MIN_MENTIONS} Auswertungen vorkommt, steht es hier.`
  );
}

function Column({
  heading,
  entries,
  titles,
  total,
  empty,
}: {
  heading: string;
  entries: GoalMentions[];
  titles: Map<string, string>;
  total: number;
  empty: string;
}) {
  // The selection travels with the link, so the goal's page counts the same
  // trainings this row does (see ProgressContext.tsx).
  const { withPeriod } = useProgressContext();

  return (
    <div className="card">
      <h3 className="recurring-heading">{heading}</h3>
      {entries.length === 0 ? (
        <p className="focus-tile-note">{empty}</p>
      ) : (
        <ul className="recurring-list">
          {entries.map((entry, index) => {
            // The catalogue title where there is one. A key whose goal has
            // since been retired still has points pointing at it, and the raw
            // key is a poor label but an honest one.
            const title = titles.get(entry.goal);
            const body = (
              <>
                <span className="recurring-rank" aria-hidden="true">
                  {index + 1}
                </span>
                <span className="recurring-body">
                  <span className="recurring-goal">{title ?? entry.goal}</span>
                  <MentionTally count={entry.count} total={total} />
                </span>
                <span className="recurring-count">
                  {entry.count} <span className="recurring-count-of">von {total}</span>
                </span>
              </>
            );

            return (
              <li key={entry.goal}>
                {/* Each row opens the goal's page, where the sentences behind the count are quoted. Not for a
                    goal the catalogue no longer knows — that page would be a dead end — and such a row gets
                    no hover either. */}
                {title ? (
                  <Link className="recurring-item" to={withPeriod(progressGoalPath(entry.goal))}>
                    {body}
                  </Link>
                ) : (
                  <span className="recurring-item">{body}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
