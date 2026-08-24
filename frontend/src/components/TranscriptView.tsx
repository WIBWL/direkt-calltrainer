import type { TurnRecord } from "../protocol";

interface TranscriptViewProps {
  transcript: TurnRecord[];
  onRestart: () => void;
}

/** The plain, unannotated post-call log of what was said (see CONTEXT.md's
 * "Transcript" entry) — not the AI-generated Feedback from ADR 0004/0015. */
export default function TranscriptView({ transcript, onRestart }: TranscriptViewProps) {
  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Gesprächsprotokoll</h1>

      {transcript.length === 0 && (
        <div className="card">
          <p>Es wurden keine Turns aufgezeichnet.</p>
        </div>
      )}

      {transcript.map((turn) => (
        <div className="card" key={turn.turn_seq}>
          <h2>Turn {turn.turn_seq}</h2>
          <p>
            <strong>Du:</strong> {turn.user_text}
          </p>
          <p>
            <strong>Persona:</strong> {turn.persona_text}
          </p>
        </div>
      ))}

      <button className="restart-button" type="button" onClick={onRestart}>
        Neue Session starten
      </button>
    </>
  );
}
