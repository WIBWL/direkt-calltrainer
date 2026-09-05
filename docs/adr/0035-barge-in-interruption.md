# ADR 0035: Eager Client-Driven Barge-In Interruption

## Status

Accepted

## Context

Waiting for the persona to finish "thinking" or speaking before the user can talk again makes the call feel like a walkie-talkie exchange rather than a real phone conversation, where interrupting mid-sentence is normal. The previous turn-based design had the client wait for a `turn.completed`/`session.ended` message before sending new audio.

## Decision

The client can send a `turn.interrupt` control message at any point during an in-flight Turn — while the persona is still generating/synthesizing ("thinking") or already streaming audio ("speaking") — and the server reacts immediately: it closes the async generator driving that Turn (cancelling only the forwarding task is not enough, since that alone does not reliably tear down the underlying pipeline generator) and returns the client to "listening" without waiting for the current reply to finish.

What of the interrupted reply is committed to the conversation history is decided by **what the user actually heard, not what the server sent**. The server streams synthesized audio ahead of playback and the client cuts the current chunk off mid-word, so "already dispatched" over-counts by whole sentences. `turn.interrupt` therefore carries `played_ms` — how many milliseconds of the reply the client actually played. The server records, per fully-synthesized chunk, the cumulative audio length at which that chunk ends; on the interrupt it commits the last chunk the client played **to its end, or at least most of the way through** (`_HEARD_FRACTION`, currently 65%, plus a small fixed grace for clock skew between the client's playback wall-time and the server's summed WAV durations) and discards the rest. A client that sends no `played_ms` falls back to committing every dispatched chunk.

The near-full allowance is not cosmetic. Without it, cutting in a second before a ~5 s sentence ends scores that sentence as unheard, so nothing is committed, the Turn reopens, and the *next* reply re-delivers the whole thing from the top — which in the transcript reads as if the persona was never interrupted at all, and in the model's context invites it to just repeat.

If nothing was heard — the interrupt landed before any chunk was substantially played, or before any audio at all — the same Turn is kept open (`_reopen_turn`) so the next recorded utterance is appended onto the pending question instead of starting a new Turn.

## Consequences

Interrupting feels instant to the user, closer to a real phone call, and the "reopened turn" semantics correctly handle "wait, also—" as one question instead of fragmenting it into two disconnected Turns. Because only heard utterances enter the history, the persona's next reply picks up from what was actually said aloud — it no longer continues from, or repeats, sentences the user never received.

In exchange, a Turn's server-side lifecycle is more stateful — it can be revisited across multiple WebSocket exchanges instead of being fully resolved by one — correct interruption depends on explicitly closing the pipeline generator rather than just cancelling the task forwarding its events, and the wire protocol now carries a client-measured playback position that the server trusts. The commit granularity is one synthesis chunk (roughly a sentence): a sentence the user heard most of is kept whole, one they heard only the first word of is dropped whole.
