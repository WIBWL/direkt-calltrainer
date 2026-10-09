import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";

import { useFocusContext } from "../FocusContext";
import { useAccount } from "../hooks/useAccount";
import type { SessionDetail, SessionTurn, TranscriptEntry } from "../protocol";
import { downloadFeedbackPdf } from "../utils/feedbackPdf";
import { initialsOf } from "../utils/initials";
import { prefersReducedMotion } from "../utils/motion";
import { callMeta } from "../utils/reportOutline";
import { formatOffset } from "../utils/time";
import { TranscriptFocusProvider } from "./TranscriptFocus";

interface FeedbackScreenProps {
  transcript: TranscriptEntry[];
  personaName: string;
  /** Where a random Scenario (F-66) is revealed too. */
  scenarioName?: string | null;
  /** Passed in: one screen polls for it, the other reads it once. */
  feedback?: ReactNode;
  /** For the file; null while generating and for an unstored call (ADR 0066). */
  detail?: SessionDetail | null;
  /** The one thing the two screens differ in. */
  actions?: ReactNode;
  /** Under the transcript: the history's delete. */
  children?: ReactNode;
}

/** Shared by the post-call screen and a past training so they cannot drift. The
 * download is the whole wrap-up, without consent the only copy (ADR 0066). */
export default function FeedbackScreen({
  transcript,
  personaName,
  scenarioName,
  feedback,
  detail,
  actions,
  children,
}: FeedbackScreenProps) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  // The transcript line a point pointed at (TranscriptFocus.tsx).
  const [focused, setFocused] = useState<number | null>(null);
  const logId = useId();
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  // The User's initials from the ID token.
  const account = useAccount();
  const { focus: picked } = useFocusContext();
  const meta = callMeta(personaName, scenarioName, detail?.reverse);

  // Without a wrap-up the button offers the protocol, not feedback.
  const complete = Boolean(detail?.feedback);

  // The panel opens first; the effect below scrolls after the render.
  const reveal = useCallback((offsetMs: number) => {
    setExpanded(true);
    setFocused(offsetMs);
  }, []);

  const focus = useMemo(() => ({ reveal, focused }), [reveal, focused]);

  useEffect(() => {
    if (focused === null || !expanded) return;
    const line = transcriptRef.current?.querySelector(`[data-offset="${focused}"]`);
    // Centred, or the line lands under the sticky header.
    line?.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }, [focused, expanded]);

  const download = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await downloadFeedbackPdf({
        transcript,
        personaName,
        scenarioName,
        detail: detail ?? null,
        goals: picked?.goals ?? [],
      });
    } catch (e) {
      console.debug("[feedback pdf] failed", e);
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const body = (
    <>
      <div className="feedback-intro">
        <h1 className="feedback-title">Ihr Gesprächsfeedback</h1>
      </div>

      {/* Here, not in the report: a Session without a wrap-up still has a case and a side (ADR 0070). */}
      <div className="feedback-meta" aria-label="Trainingsdetails">
        {meta.scenario && <span>{meta.scenario}</span>}
        {meta.scenario && (
          <span className="feedback-meta-separator" aria-hidden="true">
            ·
          </span>
        )}
        <span>{meta.reversal ? `Rollentausch: ${meta.reversal}` : meta.partner}</span>
      </div>

      {feedback}

      <div className="feedback-actions">
        {actions}

        {transcript.length > 0 && (
          <>
            <button
              type="button"
              className="back-to-start-button"
              aria-expanded={expanded}
              aria-controls={logId}
              onClick={() => setExpanded((open) => !open)}
            >
              {expanded ? "Transkript einklappen" : "Transkript ausklappen"}
            </button>

            <button
              type="button"
              className="back-to-start-button"
              disabled={busy}
              onClick={download}
            >
              {busy
                ? "PDF wird erstellt …"
                : complete
                  ? "Gesprächsfeedback herunterladen"
                  : "Transkript als PDF herunterladen"}
            </button>
          </>
        )}
      </div>

      {failed && (
        <p className="follow-up-error transcript-download-error">
          Das PDF konnte nicht erstellt werden. Bitte versuchen Sie es erneut.
        </p>
      )}

      {/* Under its button, and not rendered while closed. */}
      {expanded && transcript.length > 0 && (
        <section className="feedback-transcript-section" id={logId}>
          <div className="feedback-transcript-heading">
            <div>
              <h2 className="feedback-transcript-title">Vollständiges Transkript</h2>
            </div>

            <span className="feedback-transcript-count">{transcript.length} Beiträge</span>
          </div>

          <div className="feedback-transcript-card" ref={transcriptRef}>
            {transcript.map((entry, i) => (
              <div
                className={`transcript-line${entry.offset_ms === focused ? " is-focused" : ""}`}
                key={i}
                data-offset={entry.offset_ms}
              >
                <span className="transcript-time">{formatOffset(entry.offset_ms)}</span>

                <span className="transcript-avatar" aria-hidden="true">
                  {entry.speaker === "user" ? account.initials : initialsOf(personaName)}
                </span>

                <div className="transcript-content">
                  <div className="transcript-speaker">
                    {entry.speaker === "user" ? "Du" : personaName}
                  </div>

                  <p className="transcript-text">{entry.text}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {children}
    </>
  );

  // Without a stored transcript the points keep their plain timestamp.
  return transcript.length > 0 ? (
    <TranscriptFocusProvider value={focus}>{body}</TranscriptFocusProvider>
  ) : (
    body
  );
}

/** A just-ended call has its lines from the socket, a past one from the database. */
export function transcriptFromTurns(turns: SessionTurn[]): TranscriptEntry[] {
  return turns.map((turn) => ({
    speaker: turn.speaker,
    text: turn.transcript,
    offset_ms: turn.start_offset_ms,
  }));
}
