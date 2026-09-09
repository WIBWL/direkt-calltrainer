import { useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api";
import { useSessionHistory } from "../hooks/useSessionHistory";
import type { SessionSummary } from "../protocol";
import { formatClock, formatDateTime } from "../utils/time";
import { sessionPath } from "../routes";

/** How many rows the list shows before the user asks for the rest. Four is
 *  what a returning user actually looks for — the last handful of calls — and
 *  it keeps the sections below (data, deletion) on the same screen instead of
 *  pushing them past a history that grows without bound. */
const COLLAPSED_ROWS = 4;

/**
 * The user's past trainings (F-48), each one a row that opens the wrap-up that
 * was generated for it back then (F-13's data, without F-13's judgement — see
 * ADR 0065: this lists what happened, it does not rate it).
 *
 * One line per training on purpose. A history is read by scanning it for the
 * one call you are thinking of, so what earns its place in a row is what tells
 * two calls apart: when it was, which scenario, and with whom.
 *
 * Only the newest few are shown; the rest are one click away. Nothing is
 * withheld by that — the older rows are already loaded, the button says how
 * many there are, and expanding is what the page remembers for as long as it
 * is open.
 *
 * Deleting is offered on the row itself rather than only inside the training:
 * clearing out a handful of old calls should not mean opening and leaving each
 * one. The confirmation is what carries the weight (ADR 0066) — the deletion is
 * final and reaches the wrap-up and the figures with it.
 */
export default function SessionHistory() {
  const { sessions, total, state, hasMore, loadingMore, loadMore, removeSession } =
    useSessionHistory();
  const [expanded, setExpanded] = useState(false);

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

  const visible = expanded ? sessions : sessions.slice(0, COLLAPSED_ROWS);
  const hidden = total - visible.length;

  return (
    <>
      <ol className="session-list">
        {visible.map((session) => (
          <li key={session.session_id}>
            <SessionRow session={session} onDeleted={() => removeSession(session.session_id)} />
          </li>
        ))}
      </ol>

      {sessions.length > COLLAPSED_ROWS && (
        <button
          type="button"
          className="session-more"
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded ? "Weniger anzeigen" : `Ältere Trainings anzeigen (${hidden})`}
        </button>
      )}

      {/* Only once the list is open — under a collapsed list this would offer
          to fetch rows that are not being shown. */}
      {expanded && hasMore && (
        <button
          type="button"
          className="session-more"
          onClick={loadMore}
          disabled={loadingMore}
        >
          {loadingMore ? "Wird geladen …" : `Weitere laden (${sessions.length} von ${total})`}
        </button>
      )}
    </>
  );
}

function SessionRow({
  session,
  onDeleted,
}: {
  session: SessionSummary;
  onDeleted: () => void;
}) {
  const duration = callDuration(session);
  const feedback = feedbackChip(session);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);

  const remove = async () => {
    setDeleting(true);
    setFailed(false);
    try {
      await apiFetch(`/api/sessions/${session.session_id}`, { method: "DELETE" });
      onDeleted(); // the row goes with it, so no state to reset afterwards
    } catch (e) {
      console.debug("[delete session] failed", e);
      setFailed(true);
      setDeleting(false);
    }
  };

  const when = formatDateTime(session.started_at) ?? session.started_at;

  return (
    <div className="session-item">
      <Link to={sessionPath(session.session_id)} className="session-row">
        <span className="session-row-date">{when}</span>

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

      {/* Outside the Link, not inside it: a button nested in an anchor is
          invalid markup and clicking it would navigate as well as delete. */}
      <button
        type="button"
        className="session-row-delete"
        // The label names the training, because a screen reader meets a
        // column of otherwise identical "Löschen" buttons.
        aria-label={`Training „${session.scenario}“ vom ${when} löschen`}
        title="Training löschen"
        aria-expanded={confirming}
        // A toggle rather than a one-way trigger, and never disabled: a button
        // that disables itself on click drops keyboard focus to nowhere.
        onClick={() => !deleting && setConfirming((open) => !open)}
      >
        <TrashIcon />
      </button>

      {confirming && (
        <div className="session-row-confirm">
          <p>
            <strong>Dieses Training löschen?</strong> Gesprächsprotokoll, Kennzahlen und
            Auswertung werden entfernt. Das lässt sich nicht rückgängig machen.
          </p>
          <div className="session-row-confirm-actions">
            <button
              type="button"
              className="consent-button consent-button-danger"
              onClick={() => void remove()}
              disabled={deleting}
            >
              {deleting ? "Wird gelöscht …" : "Endgültig löschen"}
            </button>
            <button
              type="button"
              className="cancel-button"
              onClick={() => setConfirming(false)}
              disabled={deleting}
            >
              Abbrechen
            </button>
          </div>
          {failed && (
            <p className="consent-error">
              Das Training konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Bin, drawn rather than typed: no icon font, no external asset. */
function TrashIcon() {
  return (
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" focusable="false">
      <path
        d="M2.5 4h11M6.5 4V2.75h3V4M4 4l.6 9.1a.9.9 0 0 0 .9.9h5a.9.9 0 0 0 .9-.9L12 4M6.6 6.8v4.6M9.4 6.8v4.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
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
