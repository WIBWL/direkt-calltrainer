# ADR 0035: Eager Client-Driven Barge-In Interruption

## Status

Accepted

## Context

Waiting for the persona to finish "thinking" or speaking before the user can talk again makes the call feel like a walkie-talkie exchange rather than a real phone conversation, where interrupting mid-sentence is normal. The previous turn-based design had the client wait for a `turn.completed`/`session.ended` message before sending new audio.

## Decision

The client can send a `turn.interrupt` control message at any point during an in-flight Turn — while the persona is still generating/synthesizing ("thinking") or already streaming audio ("speaking") — and the server reacts immediately: it closes the async generator driving that Turn (cancelling only the forwarding task is not enough, since that alone does not reliably tear down the underlying pipeline generator) and returns the client to "listening" without waiting for the current reply to finish. If the interrupted Turn had not yet produced any audible reply, the same Turn is kept open (`_reopen_turn`) so the next recorded utterance is appended onto the pending question instead of starting a new Turn. Only words actually dispatched as audio are committed to the conversation history; anything only generated but not yet sent is discarded.

## Consequences

Interrupting feels instant to the user, closer to a real phone call, and the "reopened turn" semantics correctly handle "wait, also—" as one question instead of fragmenting it into two disconnected Turns. In exchange, a Turn's server-side lifecycle is more stateful — it can be revisited across multiple WebSocket exchanges instead of being fully resolved by one — and correct interruption depends on explicitly closing the pipeline generator, not just cancelling the task forwarding its events.
