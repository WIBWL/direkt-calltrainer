# ADR 0028: No Secondary Indexes Beyond Primary/Foreign Keys Yet

## Status

Accepted

## Context

Defining the initial schema (ADR 0026), each table needed a decision on which columns to index beyond what a primary key implicitly provides. Candidate additional indexes were already visible at this stage — e.g. `session.subject_id` (looked up per user), or `turn.session_id`/`messung.turn_id`/`befund.turn_id` (looked up per Session when assembling Feedback) — but none of the actual read/query code for these tables exists yet; the backend does not query this schema at all so far.

## Decision

The initial schema and migration declare only the constraints SQLAlchemy needs for data integrity — primary keys, foreign keys, and the two uniqueness constraints that encode real business rules (`metrik_typ.schluessel` unique; `feedback.session_id` unique, for its 1:1 relationship to Session) — and no additional secondary indexes.

## Consequences

This keeps the first migration minimal and avoids guessing at access patterns before the Session/Feedback read paths that will actually query this data exist. Foreign-key columns without an explicit index — Postgres does not automatically index the referencing side of a foreign key, unlike the referenced primary-key side — will fall back to sequential scans until a real workload identifies which lookups need one. This decision is expected to be revisited once the read side (Session history, aggregated Feedback per ADR 0023, F-13/F-48) is built against real query patterns rather than guesses.
