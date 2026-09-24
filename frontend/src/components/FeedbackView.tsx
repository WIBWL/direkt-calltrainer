import { useState, type ReactNode } from "react";

import { ApiError } from "../api";
import type { FeedbackState } from "../hooks/useSessionFeedback";
import type { SessionDetail } from "../protocol";
import type { ReverseScenario } from "../scenarioLibrary";
import { retryFeedback } from "../sessions";
import FeedbackReport from "./FeedbackReport";
import type { FollowUpActions } from "./NextSteps";

/** Everything that is not a finished wrap-up is a one-line notice. There is
 * no entry for "ready": the hook reports it only once feedback is present. */
const NOTICE: Record<string, string> = {
  loading: "Das Feedback wird erstellt. Einen Moment bitte.",
  missing: "Für dieses Gespräch wurde kein Feedback gespeichert.",
  failed:
    "Das Feedback konnte nicht erstellt werden. Das Gesprächsprotokoll unten ist davon nicht betroffen.",
};

/**
 * The post-call wrap-up (F-09/F-10/F-53): the model's narrative and the statistics it
 * was written from, the figures as evidence, never a score (ADR 0004/0049/0051). The
 * Session is polled once in `App` and handed in, so the PDF reads the same `detail`.
 */
export default function FeedbackView({
  detail,
  state,
  sessionId,
  onRetry,
  followUp,
  onReverse,
  next,
}: {
  /** The polled Session. Null while it has not arrived, and for a call that
   * was never stored. */
  detail: SessionDetail | null;
  state: FeedbackState;
  /** The Session to ask again about, where a failed wrap-up can be retried.
   *  Null on a call that was never stored — there is nothing to generate. */
  sessionId?: string | null;
  /** Poll again, once the retry has been accepted. Omitted on a screen that
   *  does not poll (the history reads once), where the retry is not offered. */
  onRetry?: () => void;
  /** Omitted where there is nowhere to act on the follow-up (F-60). */
  followUp?: FollowUpActions;
  /** Create and start the reverse of this Session (F-61, ADR 0070). Like
   * `followUp.onStart` it belongs to whoever owns the screen: the post-call
   * screen begins the call itself, the history hands the pairing to the
   * training flow. Omitted where there is nowhere to go with it. */
  onReverse?: (reverse: ReverseScenario) => void;
  /** What to play next (F-64). Shown without a wrap-up too: it needs no
   *  stored Session, so a call that was not kept still gets it. */
  next?: ReactNode;
}) {
  if (!detail?.feedback) {
    return (
      <>
        <div className="card">
          <p className="muted">{NOTICE[state]}</p>
          {/* The one state that was a dead end. The work is still possible —
              a wrap-up is written from the stored Transcript and Measurements,
              never from audio (ADR 0048/0049) — and until now the only way to
              ask for it again ran inside the container. */}
          {state === "failed" && sessionId && onRetry && (
            <RetryFeedback sessionId={sessionId} onQueued={onRetry} />
          )}
        </div>
        {next}
      </>
    );
  }
  return (
    <FeedbackReport detail={detail} followUp={followUp} onReverse={onReverse} next={next} />
  );
}

/**
 * Ask for the wrap-up once more. On a refusal it shows the server's sentence, since the
 * reasons (a job still running, nothing to summarise) are invisible here. On success
 * polling resumes at once.
 */
function RetryFeedback({
  sessionId,
  onQueued,
}: {
  sessionId: string;
  onQueued: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    setBusy(true);
    setError(null);
    try {
      await retryFeedback(sessionId);
      onQueued();
    } catch (e) {
      setError(
        e instanceof ApiError && e.detail
          ? e.detail
          : "Die Auswertung konnte nicht angefordert werden. Bitte später noch einmal versuchen.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="follow-up-button"
        disabled={busy}
        onClick={() => void ask()}
      >
        {busy ? "Wird angefordert …" : "Auswertung erneut erstellen"}
      </button>
      {error && <p className="follow-up-error">{error}</p>}
    </>
  );
}
