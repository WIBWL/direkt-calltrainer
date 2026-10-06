# ADR 0042: The Reverse's Opening Turn Is Pre-Warmed at Commitment

## Context

In a reverse (ADR 0070) the Persona speaks first, and generating that line is silence at the worst moment. Pre-warming on every selection change wasted gateway capacity and replayed stale buffered openings.

## Decision

- The opening is generated when the User commits, by leaving the selection for the microphone check, not when they select. An ordinary call is not pre-warmed (ADR 0110).
- Buffered opening audio belongs to exactly one connection. Replacing the connection discards it.

## Consequences

The gateway sees one opening per conducted call. A User who confirms the microphone instantly may hear a brief silence. The pre-warm trigger and the buffer discard must share one notion of "connection changed"; if they drift, an old opening line is heard.
