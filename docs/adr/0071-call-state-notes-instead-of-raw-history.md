# ADR 0071: The Model Reads Its Notes and the Last Exchanges, Not the Whole History

## Context

The small model loses the thread after a few exchanges when it holds forty rules and an unbounded, noisy transcript. It turned its own case facts into questions to the user.

## Decision

1. **A short, sectioned system prompt.** It keeps every decision and drops the rest of the wording. The case facts are things the caller knows and the user does not: never ask about them, never attribute them to the user.
2. **The caller's notes replace the history beyond the window.** The model receives the system prompt, the notes (framed as established fact), the last six messages verbatim, and the Turn's nudge. The full record is still kept for the guards and the transcript. The notes are rewritten in the background after each committed reply (three lines: what the user offered, what the caller still wants, settled or not), never on the reply path, and again after a barge-in trim. A failed refresh keeps the old notes.
3. **Phantom transcripts are not Turns.** A transcript that is nothing but a Whisper hallucination or a non-speech annotation gets no reply and no history entry.

## Consequences

The model's view stays the same size however long the call runs, and commitments survive as notes. Notes are rewritten from notes, so an error has no source left to be corrected against. A model that reads its own history well would not need them.
