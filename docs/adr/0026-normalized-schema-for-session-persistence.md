# ADR 0026: Normalized Relational Schema for Session Persistence

## Status

Accepted

## Context

ADR 0010 and ADR 0025 established Postgres plus SQLAlchemy for Session persistence, but not the actual shape of that data: what a Session, Turn, Persona, Scenario, or Feedback look like as durable rows. The domain glossary (`CONTEXT.md`) already defines Session, Persona, Scenario, and Feedback as first-class concepts, and ADR 0023 anticipates reading Feedback back per-Session and aggregated across Sessions (F-13, F-48) once persistence exists.

## Decision

We modeled persistence as a normalized relational schema of twelve entities, mirroring the domain glossary as closely as possible: `Persona` — together with `PersonaObjection`, which holds a Persona's typical objections as ordered rows rather than as a repeating group inside the Persona itself — plus `Scenario` and `Language` as reusable lookup/configuration entities; `Session` as the central fact table referencing them; `Turn` as one row per exchange within a Session, holding the user's utterance and the Persona's reply to it side by side rather than one row per speaker; `MetricType`/`Measurement`/`Finding` for per-turn speech analysis, each keyed against a metric-type lookup table and each describing the user's half of a Turn, since the Persona's speech is synthesized and measuring it says nothing about the user; `Feedback`/`FeedbackPoint` for the post-call summary and its individual points, referencing back to the originating Turns/Findings; and `AnalysisJob` to track async processing status per Session (see ADR 0032). Table and column names are English and follow the domain glossary in CONTEXT.md, so a term means the same thing in the schema, in the ORM and in the surrounding code. The project's user-facing content and its documentation stay German; only identifiers are English. `backend/db/models.py` is the single source of truth: both the Alembic migrations (ADR 0027) and the ER diagram (ADR 0030) are derived from it, not maintained independently. Ownership between entities is expressed twice, on purpose: as ORM-level delete cascades (`cascade="all, delete-orphan"`, with `passive_deletes=True`) on the owning relationships, and as `ON DELETE CASCADE` on the foreign keys themselves, so a plain `DELETE FROM session` behaves the same as the ORM path. The optional back-references from a FeedbackPoint use `ON DELETE SET NULL`, and foreign keys into the shared reference entities (Persona, Scenario, Language, MetricType) carry no clause at all — deleting a Persona that has stored Sessions must fail rather than take them along.

## Consequences

The schema stays legible against the domain glossary — reading a Session back means walking well-understood foreign keys rather than reconstructing meaning from a denormalized blob — and a schema change always starts in one file (`models.py`), reducing drift risk between code, migrations, and documentation. The tradeoff is a fairly wide schema (twelve tables) for an MVP, and per-turn `Measurement`/`Finding` rows can grow quickly with call volume; no partitioning, archival, or retention strategy is decided yet (see ADR 0034 for the storage and consent policy, which is not yet reflected as an enforcement mechanism in this schema).
