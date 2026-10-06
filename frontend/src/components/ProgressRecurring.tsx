import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useProgressContext } from "../ProgressContext";
import type { FocusGoal, SessionSummary } from "../protocol";
import { progressGoalPath } from "../routes";
import { MIN_MENTIONS, mentionSummary, type GoalMentions } from "../utils/goalMentions";
import InfoDetails from "./InfoDetails";
import MentionTally from "./MentionTally";
import SectionHeading from "./SectionHeading";

/** Block D: what the wrap-ups keep naming. Statements over a named denominator,
 * never a percentage (ADR 0004/0065). */
export default function ProgressRecurring({
  sessions,
  catalogue,
  practice,
}: {
  sessions: SessionSummary[];
  catalogue: FocusGoal[];
  /** Only where something recurs. */
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
          {/* Two cards: inside one border they read as one table. */}
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

          {practice}

          {/* A footnote to both lists, under the suggestion. */}
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
              Auswertung zählen nicht mit.
            </p>
          </InfoDetails>
        </>
      )}
    </section>
  );
}

function emptyText(total: number): string {
  if (total === 0) {
    return (
      "Hier steht später, was Ihre Auswertungen wiederholt nennen. Bisher liegt dafür keine " +
      "ausgewertete Aufzeichnung vor."
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
  // The selection travels with the link.
  const { withPeriod } = useProgressContext();

  return (
    <div className="card">
      <h3 className="recurring-heading">{heading}</h3>
      {entries.length === 0 ? (
        <p className="focus-tile-note">{empty}</p>
      ) : (
        <ul className="recurring-list">
          {entries.map((entry, index) => {
            // A retired goal shows its key.
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
                {/* No link for a goal the catalogue no longer knows. */}
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
