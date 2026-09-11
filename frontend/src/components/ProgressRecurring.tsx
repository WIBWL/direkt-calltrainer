import type { FocusGoal, SessionSummary } from "../protocol";
import { MIN_MENTIONS, mentionSummary, type GoalMentions } from "../utils/goalMentions";

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
 */
export default function ProgressRecurring({
  sessions,
  catalogue,
}: {
  sessions: SessionSummary[];
  /** The focus catalogue, for turning a key into its German title. Served with
   *  the selection (`GET /api/focus`), so the wording lives in one place. */
  catalogue: FocusGoal[];
}) {
  const { strengths, improvements, total } = mentionSummary(sessions);
  const titles = new Map(catalogue.map((goal) => [goal.key, goal.title]));
  const nothing = strengths.length === 0 && improvements.length === 0;

  return (
    <section className="progress-section" aria-labelledby="recurring-title">
      <div className="progress-section-head">
        <h2 id="recurring-title">Was in Ihren Auswertungen wiederkehrt</h2>
      </div>

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

          {/* Under both cards rather than inside one of them: it describes the
              counting, which is the same on either side. */}
          <p className="progress-preview-note recurring-note">
            Gezählt wird, in wie vielen Ihrer {total} ausgewerteten Trainings ein Thema genannt
            wurde, nicht wie oft es vorkam. Das ist eine Häufigkeit von Aussagen und keine
            Messung: Es steht hier, weil die Auswertungen es geschrieben haben, nicht weil etwas
            nachgemessen wurde. Aufgenommen wird ein Thema ab {MIN_MENTIONS} Nennungen, denn ein
            einzelner Punkt aus einem einzelnen Gespräch ist eine Beobachtung und kein Muster.
          </p>
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
                <Tally count={entry.count} total={total} />
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

/**
 * How many of the trainings named this, drawn.
 *
 * One pip per analysed training, filled where the theme came up. A count over a
 * denominator of three or eight is what this is, and pips say that where a bar
 * would round it into a proportion and invite reading it as a level. Above
 * `MAX_PIPS` the row of dots stops being countable at a glance, so it becomes a
 * single track instead, which is the lesser evil at that width.
 *
 * Decoration only: the figure stands beside it in words, and this carries
 * `aria-hidden` for that reason. It is a frequency of statements either way,
 * never a measurement and never a score (ADR 0065).
 */
const MAX_PIPS = 12;

function Tally({ count, total }: { count: number; total: number }) {
  if (total > MAX_PIPS) {
    const share = total > 0 ? Math.min(1, count / total) : 0;
    return (
      <span className="recurring-track" aria-hidden="true">
        <span className="recurring-track-fill" style={{ width: `${share * 100}%` }} />
      </span>
    );
  }
  return (
    <span className="recurring-pips" aria-hidden="true">
      {Array.from({ length: total }, (_, index) => (
        <span
          key={index}
          className={`recurring-pip${index < count ? " is-named" : ""}`}
        />
      ))}
    </span>
  );
}
