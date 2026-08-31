# ADR 0025: SQLAlchemy 2.0 as ORM

## Status

Accepted

## Context

With ADR 0010 establishing an in-repo PostgreSQL database, the backend needs a way to define tables and query them from Python. Candidates included raw SQL via the `psycopg` driver directly, a lightweight query builder, or a full ORM with migration tooling.

## Decision

We will use SQLAlchemy 2.0 as the ORM, in its declarative `Mapped[...]`/`mapped_column` style rather than the legacy 1.x `Column`-only style. A single shared `Base` class lives in `backend/db/base.py`, deliberately isolated from `backend/db/models.py` so that models, a future DB-session module, and Alembic (ADR 0027) can each import it independently without import cycles. Every persisted entity in `backend/db/models.py` inherits from this `Base`.

## Consequences

SQLAlchemy is a mature, widely known ORM with first-class Alembic integration (ADR 0027) and typed model classes that double as the single source of truth for both the schema and the generated ER diagram (ADR 0030). It brings more machinery than raw SQL would for a schema this size, and ties the persistence layer's query and transaction patterns to SQLAlchemy's session/unit-of-work model throughout the codebase going forward.
