# ADR 0026: Own PostgreSQL Database for Application/Progress Data

## Status

Accepted (supersedes ADR 0024)

## Context

ADR 0010 delegates persistence to the external Datenplattform for user-uploaded documents that get searched by an LLM. That does not cover application data the product itself needs to own and query directly — in particular a user's training progress over time (F-13), which the Datenplattform, built for document search, is not the right fit for. The project needs a database of its own for this.

ADR 0024 previously decided to persist no Session data at all during the MVP, and to route any persistence after the MVP through the Datenplattform under explicit user consent. That decision is superseded: the team now wants a working progress store during the MVP itself, not deferred, and not routed through the Datenplattform.

## Decision

We will run our own PostgreSQL database for application data such as training progress, separate from the Datenplattform (which remains the store for uploaded documents, per ADR 0010). Access is through SQLModel, which combines SQLAlchemy with Pydantic — the same validation library FastAPI already uses. The database runs as an additional service in the existing Docker Compose setup, alongside the Redis job queue from ADR 0020. Every completed Session turn (transcript and reply) is written to this database now, during the MVP.

## Consequences

The team now operates a second stateful service (beyond Redis), including its schema, migrations, and backups — a new operational responsibility ADR 0010 had deliberately avoided for documents. In exchange, progress data gets proper relational structure and querying, available from the MVP onward rather than deferred. Because Keycloak login (ADR 0009) isn't wired up yet, records are stored against a placeholder `user_id` for now; real per-user data requires finishing the auth integration.

This decision drops ADR 0024's consent-gating requirement without yet replacing it: data is currently written unconditionally, with no consent capture or self-service deletion. ADR 0024's underlying DSGVO concern (arc42 Kapitel 11, "Unklare Datenschutz-Umsetzung") is still real and still unresolved — it now applies to this database instead of a future Datenplattform-routed store, and needs a follow-up decision before this goes anywhere near real users.
