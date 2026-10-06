import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useSessionHistory } from "../hooks/useSessionHistory";
import type { SessionSummary } from "../protocol";
import { sessionPath } from "../routes";
import { cx } from "../utils/cx";
import { callDurationMs } from "../utils/progressStats";
import { formatClock, formatDateTime } from "../utils/time";
import { useSessionDeletion } from "./DeleteSessionPrompt";

/** Past trainings (F-48), listed without rating (ADR 0065). Deletion per row is final (ADR 0066). */
export default function SessionHistory() {
  const { sessions, total, state, hasMore, loadingMore, showMore, removeSession } =
    useSessionHistory();

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
            <SessionRow session={session} onDeleted={() => removeSession(session.session_id)} />
          </li>
        ))}
      </ol>

      {hasMore && (
        <button
          type="button"
          className="session-more"
          onClick={showMore}
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
  const deletion = useSessionDeletion(session.session_id, onDeleted);
  const binRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const wasConfirming = useRef(false);

  const when = formatDateTime(session.started_at) ?? session.started_at;

  // Focus moves to the cross, not the check, so a second Enter cannot delete.
  useEffect(() => {
    if (confirming) cancelRef.current?.focus();
    else if (wasConfirming.current) binRef.current?.focus();
    wasConfirming.current = confirming;
  }, [confirming]);

  const cancel = () => {
    if (!deletion.deleting) setConfirming(false);
  };

  return (
    <div className="session-item">
      <Link to={sessionPath(session.session_id)} className="session-row">
        <span className="session-row-date">{when}</span>

        <span className="session-row-main">
          <span className="session-row-title">{session.scenario}</span>
          <span className="session-row-persona">
            {session.persona}
            {session.reverse && (
              // ADR 0070: otherwise two rows on one Scenario look alike.
              <span className="chip chip-neutral">Rollentausch</span>
            )}
            {session.status === "aborted" && (
              <span className="chip chip-neutral">abgebrochen</span>
            )}
            <span className={`chip ${feedback.tone}`}>{feedback.label}</span>
          </span>
        </span>

        {duration && <span className="session-row-duration">{duration}</span>}

        <span className="session-row-chevron" aria-hidden="true" />
      </Link>

      {/* Outside the Link: no button inside an anchor. All three stay mounted, hidden by
          `visibility`, so the bin can animate and hidden controls leave the tab order. */}
      <div
        className={cx("session-row-actions", confirming && "is-confirming")}
        role="group"
        aria-label={`Training „${session.scenario}“ vom ${when}`}
        onKeyDown={(event) => {
          if (event.key === "Escape" && confirming) cancel();
        }}
      >
        <button
          ref={binRef}
          type="button"
          className="session-row-delete"
          // A screen reader meets a column of otherwise identical buttons.
          aria-label={`Training „${session.scenario}“ vom ${when} löschen`}
          title="Training löschen"
          onClick={() => setConfirming(true)}
        >
          <TrashIcon />
        </button>

        <button
          type="button"
          className="session-row-yes"
          aria-label={`Endgültig löschen: Gesprächsprotokoll, Kennzahlen und Auswertung werden entfernt`}
          title="Endgültig löschen"
          // Never `disabled`: that drops the focus.
          aria-busy={deletion.deleting}
          onClick={() => !deletion.deleting && void deletion.remove()}
        >
          <CheckIcon />
        </button>

        <button
          ref={cancelRef}
          type="button"
          className="session-row-no"
          aria-label="Abbrechen"
          title="Abbrechen"
          onClick={cancel}
        >
          <CrossIcon />
        </button>
      </div>

      {deletion.failed && (
        <p className="session-row-error consent-error" role="alert">
          Das Training konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.
        </p>
      )}
    </div>
  );
}

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

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" focusable="false">
      <path
        d="M3.2 8.4 6.5 11.5 12.8 4.8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" focusable="false">
      <path
        d="M4.5 4.5l7 7M11.5 4.5l-7 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** A just-ended Session has a wrap-up on its way (ADR 0019); a failed job never will. */
function feedbackChip(session: SessionSummary): { label: string; tone: string } {
  if (session.has_feedback) {
    return { label: "Feedback erstellt", tone: "chip-success" };
  }
  if (session.feedback_status === "queued" || session.feedback_status === "running") {
    return { label: "Feedback wird erstellt", tone: "chip-pending" };
  }
  return { label: "kein Feedback verfügbar", tone: "chip-absent" };
}

function callDuration(session: SessionSummary): string | null {
  const ms = callDurationMs(session);
  return ms === null ? null : formatClock(ms / 1000);
}
