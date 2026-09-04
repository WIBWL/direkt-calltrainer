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
      <div className="eyebrow">Calltrainer</div>
      <h1>Ihr Feedback</h1>
      {feedback}

      <h2>Gesprächsprotokoll</h2>

      {transcript.length === 0 ? (
        <div className="card">
          <p>Es wurden keine Turns aufgezeichnet.</p>
        </div>
      ) : (
        <div className="card">
          {transcript.map((entry, i) => (
            <p className="transcript-line" key={i}>
              <span className="transcript-time">{formatOffset(entry.offset_ms)}</span>
              <span>
                <strong>{entry.sprecher === "nutzer" ? "Du" : personaName}:</strong> {entry.text}
              </span>
            </p>
          ))}
        </div>
      )}

      <button className="restart-button" type="button" onClick={onRestart}>
        Neue Session starten
      </button>
    </>
  );
}
