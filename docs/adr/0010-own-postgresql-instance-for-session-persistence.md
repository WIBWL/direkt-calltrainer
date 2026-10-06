# ADR 0010: Own PostgreSQL Instance for Session Persistence

## Context

Session data needs a durable store. The project's Data Platform moves data but does not retain it.

## Decision

The application runs its own PostgreSQL 17 for everything it persists, reached through one `POSTGRES_URL`. Alembic uses the same URL builder, so migrations cannot hit a different database. Audio is never stored (ADR 0048).

## Consequences

The project owns its schema, migrations and retention, and full control over reading and deleting data. The stored data is transcripts and numbers, not recordings.
