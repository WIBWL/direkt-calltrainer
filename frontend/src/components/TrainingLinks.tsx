import { Link } from "react-router-dom";

import type { SessionSummary } from "../protocol";
import { sessionPath } from "../routes";
import { formatDateTime } from "../utils/time";

/**
 * The trainings behind one cell, each a link into itself.
 *
 * The calendar and the variety grid both describe what somebody did and, until
 * this existed, both ended there: a cell said "2 Trainings" and the only way to
 * those two was the history in the profile, by date, by hand. That is the one
 * block on the progress screen from which nothing followed, against the rule
 * the concept takes from Verbert et al. — a block nothing follows from does not
 * belong on the screen.
 *
 * Details on demand rather than a route of its own: the list is two or three
 * rows, it belongs beside the cell it explains, and a `/fortschritt/tag/…` page
 * would be a third level for something the second already holds.
 *
 * It states what it is showing in its own heading. The list appears some way
 * from the cell that was pressed — under the calendar, under the grid — so
 * "Trainings am 14. September" is what connects the two, and it is also what a
 * screen reader hears when focus moves here.
 */
export default function TrainingLinks({
  title,
  sessions,
}: {
  /** What these trainings have in common, as a sentence. */
  title: string;
  sessions: SessionSummary[];
}) {
  if (sessions.length === 0) return null;

  return (
    <div className="training-links">
      <p className="training-links-title">{title}</p>
      <ul>
        {sessions.map((session) => (
          <li key={session.session_id}>
            <Link to={sessionPath(session.session_id)}>
              <span className="training-links-when">
                {formatDateTime(session.started_at) ?? session.started_at}
              </span>
              <span className="training-links-what">
                {session.scenario} · {session.persona}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
