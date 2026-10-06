# ADR 0016: One Retry, Then Graceful Session End on Pipeline Failure

## Context

Each turn chains STT, dialogue generation and TTS, and any of them can fail.

## Decision

A failed step is retried once. If the retry fails too, the call ends cleanly with a non-technical message.

## Consequences

Transient blips are absorbed and a real outage ends the call predictably. There is no per-turn recovery.
