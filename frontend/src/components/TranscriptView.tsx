import type { TurnRecord } from "../protocol";

interface TranscriptViewProps {
  transcript: TurnRecord[];
  personaName: string;
  onRestart: () => void;
}

/** The plain, unannotated post-call log of what was said (see CONTEXT.md's
 * "Transcript" entry) — not the AI-generated Feedback from ADR 0004/0015. */
export default function TranscriptView({ transcript, personaName, onRestart }: TranscriptViewProps) {
  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Gesprächsprotokoll</h1>

      {transcript.length === 0 && (
        <div className="card">
          <p>Es wurden keine Turns aufgezeichnet.</p>
        </div>
      )}

      {transcript.map((turn, i) => {
        // Each Turn record stores the user's reply to the *previous* Turn's
        // persona line alongside its own (new) persona line (see Turn's
        // docstring in backend/session/models.py) — so a card that reads
        // naturally as one exchange pairs this Turn's persona line with the
        // *next* Turn's user_text, not its own.
        const userReply = transcript[i + 1]?.user_text;
        return (
          <div className="card" key={turn.turn_seq}>
            {turn.persona_text && (
              <p>
                <strong>{personaName}:</strong> {turn.persona_text}
              </p>
            )}
            {userReply && (
              <p>
                <strong>Du:</strong> {userReply}
              </p>
            )}
          </div>
        );
      })}

      <button className="restart-button" type="button" onClick={onRestart}>
        Neue Session starten
      </button>
    </>
  );
}
