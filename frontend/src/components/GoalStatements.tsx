import { Link } from "react-router-dom";

import { sessionPath } from "../routes";
import type { GoalStatement } from "../utils/goalMentions";
import { formatDate } from "../utils/time";

/** Quoted, newest first, each linking to its training; no summary or trend (ADR 0004/0065). */
export default function GoalStatements({
  statements,
  title = "Was Ihre Auswertungen dazu geschrieben haben",
  titleId,
}: {
  statements: GoalStatement[];
  title?: string;
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
                {/* Written out: a green dot would grade the call (ADR 0065). */}
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
