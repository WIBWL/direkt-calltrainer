import { Link } from "react-router-dom";

import type { SessionSummary } from "../protocol";
import { sessionPath } from "../routes";
import { formatDateTime } from "../utils/time";

/**
 * The trainings behind one calendar or variety-grid cell, each a link, so those blocks lead somewhere. Shown in
 * place rather than as a route of its own. Its heading ("Trainings am 14. September") ties the list to the
 * pressed cell and is what a screen reader hears.
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
