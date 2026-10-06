# ADR 0034: Session Data Is Written Once, at Session End

## Context

A blocking database call in the turn loop would stall the event loop that streams audio. The orchestrator already holds the whole call in memory.

## Decision

- A Session is stored once, after the call, in one transaction, off the event loop, and only with consent (ADR 0066).
- A call that ends by disconnect is stored as `aborted`, and every other call as `completed`. Anything that counts trainings counts only `completed`, through one function. Anything that lists them shows both.
- Separately, a call shorter than 60 s is left out of the progress series, whatever its status, because its figures describe almost nothing. The screen and the report say how many were set aside.

## Consequences

The live call cannot fail because of the database; an outage means "ran but not recorded". A closed tab still leaves a readable record.
