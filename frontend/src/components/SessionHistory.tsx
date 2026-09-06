import { Link } from "react-router-dom";

import { useSessionHistory } from "../hooks/useSessionHistory";
import type { SessionSummary } from "../protocol";
import { formatClock, formatDateTime } from "../utils/time";
import { sessionPath } from "../routes";

/**
 * The user's past trainings (F-48), each one a row that opens the wrap-up that
 * was generated for it back then (F-13's data, without F-13's judgement — see
 * ADR 0065: this lists what happened, it does not rate it).
 *
 * One line per training on purpose. A history is read by scanning it for the
 * one call you are thinking of, so what earns its place in a row is what tells
 * two calls apart: when it was, which scenario, and with whom.
 */
export default function SessionHistory() {
  const { sessions, total, state, hasMore, loadingMore, loadMore } = useSessionHistory();

  if (state === "loading") {
    return <p className="muted">Trainings werden geladen …</p>;
  }

  if (state === "failed") {
    return <p className="muted">Ihre Trainings konnten nicht geladen werden.</p>;
  }

  if (sessions.length === 0) {
    return (
      <p className="muted">
        Sie haben noch kein Training abgeschlossen. Ein Gespräch wird erst gespeichert, wenn
        Sie es zu Ende führen.
      </p>
    );
  }

  return (
    <>
      <ol className="session-list">
        {sessions.map((session) => (
          <li key={session.session_id}>
            <SessionRow session={session} />
          </li>
        ))}
      </ol>

      {hasMore && (
        <button
          type="button"
          className="session-more"
          onClick={loadMore}
          disabled={loadingMore}
        >
          {loadingMore ? "Wird geladen …" : `Weitere anzeigen (${sessions.length} von ${total})`}
        </button>
      )}
    </>
  );
}

function SessionRow({ session }: { session: SessionSummary }) {
  const duration = callDuration(session);
  const feedback = feedbackChip(session);

  return (
    <Link to={sessionPath(session.session_id)} className="session-row">
      <span className="session-row-date">{formatDateTime(session.started_at) ?? session.started_at}</span>

      <span className="session-row-main">
        <span className="session-row-title">{session.scenario}</span>
        <span className="session-row-persona">
          {session.persona}
          {session.status === "aborted" && (
            // Worth saying, because it explains a short call or a missing
            // wrap-up — but stated, not warned about.
            <span className="chip chip-neutral">abgebrochen</span>
          )}
          <span className={`chip ${feedback.tone}`}>{feedback.label}</span>
        </span>
      </span>

      {duration && <span className="session-row-duration">{duration}</span>}

      <span className="session-row-chevron" aria-hidden="true" />
    </Link>
  );
}

/**
 * What the row promises when it is clicked.
 *
 * Three states, not two: a Session that ended a moment ago genuinely has a
 * wrap-up on its way (ADR 0019), and labelling that "kein Feedback" would be
 * wrong for as long as it takes the worker to run. A job that failed, by
 * contrast, will not produce anything later — saying so is the whole point,
 * because the screen used to imply the opposite.
 */
function feedbackChip(session: SessionSummary): { label: string; tone: string } {
  if (session.has_feedback) {
    return { label: "Feedback erstellt", tone: "chip-success" };
  }
  if (session.feedback_status === "queued" || session.feedback_status === "running") {
    return { label: "Feedback wird erstellt", tone: "chip-pending" };
  }
  return { label: "kein Feedback verfügbar", tone: "chip-absent" };
}

/** How long the call ran, as mm:ss. Null where it has no recorded end, which
 *  a Session cut short by a pipeline failure legitimately may not. */
function callDuration(session: SessionSummary): string | null {
  if (!session.ended_at) return null;
  const started = new Date(session.started_at).getTime();
  const ended = new Date(session.ended_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(ended) || ended < started) return null;
  return formatClock((ended - started) / 1000);
}
