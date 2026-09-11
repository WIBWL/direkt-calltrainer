import type { ReactNode } from "react";

import type { FocusGoal, SessionSummary } from "../protocol";
import { MIN_MENTIONS, mentionSummary, type GoalMentions } from "../utils/goalMentions";
import InfoDetails from "./InfoDetails";
import MentionTally from "./MentionTally";
import SectionHeading from "./SectionHeading";

/**
 * Block D of the dashboard: what the wrap-ups keep coming back to.
 *
 * The only part of this screen that goes beyond plain display, and the reason
 * it is allowed to: it invents nothing. The wrap-ups already wrote points of
 * two kinds, and each point now carries the focus goal it is about, so this
 * counts what the wrap-ups said. "The closing was named as an improvement in 4
 * of 8" is a frequency of statements, not a measurement of a person and not a
 * mark across trainings, which is what keeps it inside ADR 0004 and ADR 0065.
 *
 * That distinction is fragile in the reading even when it is sound in the
 * data, so the wording carries it: "genannt" throughout, never "war" or
 * "ist"; a count over a named denominator, never a percentage; and no
 * ordering language beyond most-mentioned first.
 *
 * This replaces a labelled placeholder. Until the assignment existed the area
 * was laid out with invented entries and a "Beispiel" chip, because inventing
 * a plausible weakness under somebody's own name is the worst thing this
 * screen could do and an empty stretch of page discusses nothing. It is real
 * now, so the placeholder is gone rather than kept alongside.
 *
 * The practice suggestion (block E) is the third card in the same row, beside
 * the improvements it is drawn from. Stacked under this block it read as a
 * separate section at the foot of the page; beside it, the ground and the offer
 * are one glance. It is handed in rather than built here because it has its own
 * data to fetch and its own reasons to render nothing, and the grid simply
 * closes up when it does.
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
        eyebrow="WAS GENANNT WURDE"
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
            {practice}
          </div>

          {/* Under the cards rather than inside one of them: it describes the
              counting, which is the same on either side. One sentence stays in
              view -- that this is what was written and not what was measured is
              the half a reader must not miss -- and the rules of the count move
              behind the "i", as on every other screen of the app. */}
          <p className="progress-preview-note recurring-note">
            Gezählt wird, was Ihre Auswertungen geschrieben haben, nicht was gemessen wurde.
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
 * What stands here before there is anything to count.
 *
 * Three different reasons for an empty block, and they are worth telling
 * apart: no trainings analysed at all, some analysed but nothing said twice,
 * and wrap-ups that predate the assignment. The third is invisible in the data
 * (an old wrap-up and one where nothing fitted both carry no tags), so it is
 * folded into the first sentence rather than claimed.
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
  return (
    <div className="card recurring-card">
      <h3 className="recurring-heading">{heading}</h3>
      {entries.length === 0 ? (
        <p className="focus-tile-note">{empty}</p>
      ) : (
        <ul className="recurring-list">
          {entries.map((entry, index) => (
            <li className="recurring-item" key={entry.goal}>
              <span className="recurring-rank" aria-hidden="true">
                {index + 1}
              </span>
              <span className="recurring-body">
                <span className="recurring-goal">
                  {/* The catalogue title where there is one. A key whose goal
                      has since been retired still has points pointing at it,
                      and the raw key is a poor label but an honest one. */}
                  {titles.get(entry.goal) ?? entry.goal}
                </span>
                <MentionTally count={entry.count} total={total} />
              </span>
              <span className="recurring-count">
                {entry.count} <span className="recurring-count-of">von {total}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
