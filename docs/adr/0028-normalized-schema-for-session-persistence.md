# ADR 0028: Normalized Relational Schema for Session Persistence

## Status

Accepted

## Context

ADR 0026 and ADR 0027 established Postgres plus SQLAlchemy for Session persistence, but not the actual shape of that data: what a Session, Turn, Persona, Szenario, or Feedback look like as durable rows. The domain glossary (`CONTEXT.md`) already defines Session, Persona, Scenario, and Feedback as first-class concepts, and ADR 0024 anticipates reading Feedback back per-Session and aggregated across Sessions (F-11, F-13) once persistence exists.

## Decision

We modeled persistence as a normalized relational schema of ten entities, mirroring the domain glossary as closely as possible: `Persona`, `Szenario`, and `Sprache` as reusable lookup/configuration entities; `Session` as the central fact table referencing them; `Turn` as one row per utterance within a Session; `MetrikTyp`/`Messung`/`Befund` for per-turn speech analysis, each keyed against a metric-type lookup table; `Feedback`/`Feedbackpunkt` for the post-call summary and its individual points, referencing back to the originating Turns/Befunde; and `AnalysisJob` to track async processing status per Session (see ADR 0034). Table and column names are German, matching the rest of the project's German-language domain vocabulary and documentation conventions. `backend/db/models.py` is the single source of truth: both the Alembic migrations (ADR 0029) and the ER diagram (ADR 0032) are derived from it, not maintained independently.

## Consequences

The schema stays legible against the domain glossary — reading a Session back means walking well-understood foreign keys rather than reconstructing meaning from a denormalized blob — and a schema change always starts in one file (`models.py`), reducing drift risk between code, migrations, and documentation. The tradeoff is a fairly wide schema (ten tables) for an MVP, and per-turn `Messung`/`Befund` rows can grow quickly with call volume; no partitioning, archival, or retention strategy is decided yet (see ADR 0024 for the consent/retention policy, which is not yet reflected as an enforcement mechanism in this schema).
