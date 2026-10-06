# ADR 0101: Four Structural Proposals Declined, So That They Are Not Proposed Again

## Context

Each of these looks like an improvement to a reviewer reading the code cold, because the reason against it isn't visible where the code is.

## Decision

1. **The metric inventory does not absorb readings or segment membership.** Readings are derived on read, apart from stored measurements (ADR 0091). The segment list sits with its reasons in `segments.py`. A missing explanation is already caught by a test.
2. **The frontend keeps the socket's transcript and the stored detail apart.** Without consent, the transcript is the only copy; a joined record would be optional in every field but one.
3. **The Scenario listing keeps its server-side order**, which `/next`, the suggestions and the first selectable card all read. A Scenario's "kind" is decided where each different question is asked.
4. **The interruptible Turn stays in `session_ws.py`.** Every ordering in the barge-in race is load-bearing and pinned by a test; an interface would move them without making them safer.

## Consequences

A repeat proposal can be answered by pointing here. If the ground under one changes (a third route of the ADR 0100 kind, stored Sessions without consent, a smaller metrics module), it is worth reopening.
