import type React from "react";

import type { TranscriptEntry } from "../protocol";
import { formatOffset } from "../utils/time";

interface TranscriptViewProps {
  transcript: TranscriptEntry[];
  personaName: string;
  onRestart: () => void;
  /** The AI-generated wrap-up, shown above the log. Passed in rather than
   * fetched here, so this component stays the plain Transcript it is. */
  feedback?: React.ReactNode;
}

/** The plain, unannotated post-call log of what was said (see CONTEXT.md's
 * "Transcript" entry) — not the AI-generated Feedback from ADR 0004/0014.
 *
 * One line per utterance, in the order spoken, each stamped with when it
 * started. The server flattens the exchanges, so the ordering lives in one
 * place rather than being reconstructed here (ADR 0051). */
export default function TranscriptView({
  transcript,
  personaName,
  onRestart,
  feedback,
}: TranscriptViewProps) {
  return (
    <>
      <div className="feedback-intro">
        <div className="eyebrow">TRAINING ABGESCHLOSSEN</div>
        <h1 className="feedback-title">Ihr Gesprächsfeedback</h1>
      </div>
      {feedback}

      <section className="feedback-transcript-section">
        <div className="feedback-transcript-heading">
          <div>
            <div className="feedback-transcript-eyebrow">GESPRÄCH IM DETAIL</div>
            <h2 className="feedback-transcript-title">Vollständiges Transkript</h2>
          </div>

          <span className="feedback-transcript-count">
            {transcript.length} Beiträge
          </span>
        </div>

        {transcript.length === 0 ? (
          <div className="feedback-transcript-card">
            <p className="transcript-empty">Es wurden keine Beiträge aufgezeichnet.</p>
          </div>
        ) : (
          <div className="feedback-transcript-card">
            {transcript.map((entry, i) => (
              <div className="transcript-line" key={i}>
                <span className="transcript-time">
                  {formatOffset(entry.offset_ms)}
                </span>

                <span className="transcript-avatar" aria-hidden="true">
                  {entry.speaker === "user"
                    ? "D"
                    : personaName.trim().charAt(0).toUpperCase()}
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
        )}
      </section>

      <div className="feedback-actions">
        <button className="restart-button" type="button" onClick={onRestart}>
          Zur Vorbereitung
        </button>
      </div>
    </>
  );
}
