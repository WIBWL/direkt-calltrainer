# ADR 0035: Eager Client-Driven Barge-In Interruption

## Status

Accepted

## Context

Waiting for the persona to finish "thinking" or speaking before the user can talk again makes the call feel like a walkie-talkie exchange rather than a real phone conversation, where interrupting mid-sentence is normal. The previous turn-based design had the client wait for a `turn.completed`/`session.ended` message before sending new audio.

## Decision

The client can send a `turn.interrupt` control message at any point during an in-flight Turn — while the persona is still generating/synthesizing ("thinking") or already streaming audio ("speaking") — and the server reacts immediately: it closes the async generator driving that Turn (cancelling only the forwarding task is not enough, since that alone does not reliably tear down the underlying pipeline generator) and returns the client to "listening" without waiting for the current reply to finish.

What of the interrupted reply is committed to the conversation history is decided by **what the user actually heard, not what the server sent**. The server streams synthesized audio ahead of playback, so "already dispatched" over-counts by whole sentences. `turn.interrupt` therefore carries `played_ms` — how many milliseconds of the reply the client actually played. The server records, per fully-synthesized chunk (roughly a sentence), the cumulative audio length at which that chunk ends and the chunk's own text. On the interrupt it commits every sentence whose audio played to its end, **plus a proportional word-prefix of the sentence the user cut off**: playback time maps onto characters spoken closely enough at a near-constant TTS rate, so the fraction of that sentence's audio that played picks the cut point, snapped back to a word boundary (a word still in the persona's mouth does not count as spoken). A small fixed grace (`_BARGE_IN_GRACE_MS`) covers clock skew between the client's playback wall-time and the server's summed WAV durations and doubles as the benefit of the doubt on that last sentence. A client that sends no `played_ms` falls back to committing every dispatched chunk.

Word-level rather than sentence-level: cutting in three words into a long sentence should leave three words in the transcript, not the whole sentence as if the persona had finished it. The transcript is meant to be exactly what was said aloud.

If nothing was heard — the interrupt landed before any word of the first sentence, or before any audio at all — the same Turn is kept open (`_reopen_turn`) so the next recorded utterance is appended onto the pending question instead of starting a new Turn.

**A barge-in over a reply's tail is trimmed too.** The server streams a reply's audio well ahead of playback, so it routinely finishes *and its turn generator returns* while the client is still speaking the tail — and a user who talks over that tail sends `turn.interrupt` after the reply is already in the history, where the generator teardown has nothing left to finalize. That interrupt is therefore applied directly to the committed reply, wherever it lands: `note_barge_in` trims when the interrupt reaches the still-live turn loop, `note_late_barge_in` when `_run_session` picks it up between Turns. Either way the history entry *and* `persona_text` are trimmed **together, in step** by the same "what was heard" calculation — the model never reads from more than the user heard, and the stored history can never disagree with the Transcript. The trim only ever shrinks (a stale re-entry with no played position of its own recomputes the full text and leaves the trimmed reply alone). If the interrupt reports that essentially nothing played, the committed reply is dropped and the Turn reopens, exactly as for an in-flight interrupt.

## Consequences

Interrupting feels instant to the user, closer to a real phone call, and the "reopened turn" semantics correctly handle "wait, also—" as one question instead of fragmenting it into two disconnected Turns. Because only heard utterances enter the history — whether the interrupt lands mid-generation or over the tail of an already-committed reply — the persona's next reply picks up from what was actually said aloud, and the post-call Transcript shows only what the user heard, never the full generated reply.

In exchange, a Turn's server-side lifecycle is more stateful — it can be revisited across multiple WebSocket exchanges instead of being fully resolved by one — correct interruption depends on explicitly closing the pipeline generator rather than just cancelling the task forwarding its events, and the wire protocol now carries a client-measured playback position that the server trusts. Where inside the cut-off sentence the transcript ends is an estimate (fraction of that sentence's audio played → fraction of its characters → nearest word boundary), not a measured word timestamp — the TTS gives no per-word timing — so it can be a word or two off; the fixed grace biases that toward keeping slightly more than was strictly heard.
