# ADR 0017: One Retry, Then Graceful Session End on Pipeline Failure

## Status

Accepted

## Context

The Session loop chains three calls to a single external gateway (EFRE-Direkt, ADR 0011) per turn: STT, dialogue generation, TTS (ADR 0013). arc42 flags the resulting availability/fault-tolerance behavior as an explicit gap (Kapitel 6). Any of the three steps can fail mid-turn, e.g. on a gateway timeout.

## Decision

We will retry a failed pipeline step once automatically. If the retry also fails, we will end the Session cleanly and show the user a clear, non-technical message, rather than leaving the Session hanging or exposing a raw error.

## Consequences

Short transient blips against the single university-hosted gateway are absorbed without disrupting the user, while a real outage ends the Session predictably instead of hanging indefinitely. The tradeoff: a failure past the retry always ends the whole Session — there is no per-turn recovery that lets the user simply try that turn again and keep going.
