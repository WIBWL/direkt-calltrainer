# ADR 0026: Normalized Relational Schema for Session Persistence

## Context

Stored Sessions must be read back per Session and across Sessions.

## Decision

The schema is normalized and mirrors the domain glossary, with English identifiers. The main parts:

- Reference tables: Persona with its objections, Scenario, Language and MetricType.
- **Session** is the central row.
- **Turn** has one row per utterance, ordered within the Session.
- **Measurement** and **Finding** hang off the Session (ADR 0051).
- **Feedback** and **FeedbackPoint** hold the wrap-up.
- **AnalysisJob** tracks the wrap-up's status.

Ownership is expressed both as ORM cascades and as `ON DELETE CASCADE`, so raw SQL behaves like the ORM. A FeedbackPoint's back-references are `SET NULL`. Foreign keys into reference tables carry no `ondelete`, so deleting a Persona or Scenario that a stored Session uses fails.

## Consequences

The schema is legible against the glossary, and every schema change starts in `models.py`. It is fairly wide for its size.
