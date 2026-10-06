# ADR 0035: Eager Client-Driven Barge-In Interruption

## Context

Waiting for the Persona to finish before the user can talk makes the call feel like walkie-talkie. On a real phone, people interrupt.

## Decision

- The client may send `turn.interrupt` at any time during a Turn. The server closes the generator driving the Turn (cancelling the forwarding task alone does not tear it down) and returns to listening.
- **The client stops playback sharply, which takes two guards.** Playback drops already-scheduled sources and, through an epoch counter, any chunk still decoding. The socket stops forwarding audio frames until the next reply starts.
- **Only what was heard enters the history.** `turn.interrupt` carries `played_ms`. Sentences that played to their end are kept, plus a proportional word prefix of the sentence that was cut off, with a small grace. If nothing was heard, the Turn reopens, so the next utterance extends the same question.
- **The same trim applies to late interrupts** over a reply's tail that is already committed. The history and `persona_text` are always trimmed together, and only ever shrink.
- **The model is told it was cut off.** The trimmed history line ends in a dash, and the next Turn carries the interrupted nudge, placed before the user's message. Replies that resume the cut-off sentence or echo the user's opening words are filtered out before synthesis. If nothing remains, the reply is re-asked once.
- The transcript marks a cut-off Persona line `[unterbrochen]`. The model never sees the marker.
- An interrupt after the goodbye ends the call instead of reviving it.

## Consequences

Interrupting feels instant, and the transcript holds only what was heard. The Turn lifecycle is stateful across messages, and the server trusts a client-measured position. The cut point is an estimate and can be a word off.
