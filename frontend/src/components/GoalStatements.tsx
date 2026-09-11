import { Link } from "react-router-dom";

import { sessionPath } from "../routes";
import type { GoalStatement } from "../utils/goalMentions";
import { formatDate } from "../utils/time";

/**
 * What the wrap-ups wrote about a goal, quoted, newest training first.
 *
 * The dashboard's second level owes the reader this. Block D counts mentions
 * and a focus tile says "in 4 von 8 Auswertungen genannt", which is a number
 * the user has no way to check unless the sentences behind it are reachable;
 * and for the six goals with no measurement of their own the sentences are the
 * whole of what exists (docs/dashboard-konzept.md, section 7).
 *
 * Deliberately a quotation and nothing else. No summary across the entries, no
 * "is getting better", no count in a heading that would read as a score — the
 * counting happens on the overview, under wording ADR 0080 settled, and
 * repeating it here in a second form would be a second claim. Each entry says
 * which training it came from and links into it, because a sentence about a
 * call is only readable next to the call.
 *
 * Strength and improvement are both shown and labelled. Showing only the
 * improvements would turn a record of what was said into a list of faults,
 * which is exactly the reading ADR 0004 and ADR 0065 refuse.
 */
export default function GoalStatements({
  statements,
  title = "Was Ihre Auswertungen dazu geschrieben haben",
  titleId,
}: {
  statements: GoalStatement[];
  title?: string;
  /** For the `aria-labelledby` of the section around it, where a page has more
   *  than one of these. */
  titleId?: string;
}) {
  if (statements.length === 0) return null;

  return (
    <>
      <h2 id={titleId}>{title}</h2>
      <div className="card">
        <ul className="goal-statements">
          {statements.map((statement, index) => (
            <li key={`${statement.sessionId}-${index}`} className="goal-statement">
              <p className="goal-statement-text">{statement.text}</p>
              <p className="goal-statement-source">
                {/* Written out and not colour-coded: a green dot beside a
                    sentence would grade the call (ADR 0065). */}
                <span className="goal-statement-kind">
                  {statement.kind === "strength" ? "Als Stärke genannt" : "Als Verbesserung genannt"}
                </span>{" "}
                in{" "}
                <Link to={sessionPath(statement.sessionId)}>
                  {statement.scenario} am {formatDate(statement.at) ?? statement.at}
                </Link>
              </p>
            </li>
          ))}
        </ul>
      </div>

      <p className="muted">
        Das sind die Sätze aus Ihren Auswertungen, unverändert. Geschrieben hat sie ein
        Sprachmodell nach dem jeweiligen Gespräch. Sie sind eine Beschreibung dieses einen
        Gesprächs und keine Messung.
      </p>
    </>
  );
}
