import { useState, type ReactNode } from "react";

import { ApiError } from "../api";
import type { FeedbackState } from "../hooks/useSessionFeedback";
import type { SessionDetail } from "../protocol";
import type { ReverseScenario } from "../scenarioLibrary";
import { retryFeedback } from "../sessions";
import FeedbackReport from "./FeedbackReport";
import type { FollowUpActions } from "./NextSteps";

/** No "ready": the hook reports it only once feedback is present. */
const NOTICE: Record<string, string> = {
  loading: "Das Feedback wird erstellt. Einen Moment bitte.",
  missing: "Für dieses Gespräch wurde kein Feedback gespeichert.",
  failed:
    "Das Feedback konnte nicht erstellt werden. Das Gesprächsprotokoll unten ist davon nicht betroffen.",
};

/** The post-call wrap-up (F-09/F-10/F-53): narrative and figures, never a score (ADR 0004/0049/0051). */
export default function FeedbackView({
  detail,
  state,
  sessionId,
  onRetry,
  followUp,
  onReverse,
  next,
}: {
  /** Null while arriving, and for an unstored call. */
  detail: SessionDetail | null;
  state: FeedbackState;
  /** Null for an unstored call. */
  sessionId?: string | null;
  /** Omitted where nothing polls (the history), and the retry with it. */
  onRetry?: () => void;
  followUp?: FollowUpActions;
  /** F-61 (ADR 0070); belongs to whoever owns the screen. */
  onReverse?: (reverse: ReverseScenario) => void;
  /** F-64. Needs no stored Session. */
  next?: ReactNode;
}) {
  if (!detail?.feedback) {
    return (
      <>
        <div className="card">
          <p className="muted">{NOTICE[state]}</p>
          {/* Written from stored data, never audio (ADR 0049), so it can be asked again. */}
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

/** Shows the server's refusal sentence; on success polling resumes. */
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
