# ADR 0025: SQLAlchemy 2.0 as ORM

## Context

The backend needs to define and query tables from Python.

## Decision

SQLAlchemy 2.0 in the typed `Mapped[...]` style, with one shared `Base`, kept apart from the models to avoid import cycles.

## Consequences

The models are the single source for the schema, the migrations (ADR 0027) and the ER diagram. Persistence is tied to SQLAlchemy's unit-of-work model.
