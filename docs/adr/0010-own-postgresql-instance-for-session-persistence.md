# ADR 0010: Own PostgreSQL Instance for Session Persistence

## Status

Proposed

## Context

The product needs a durable store for Session data — Session metadata, Turn text, speech-analysis results, Feedback. An external Data Platform service exists in the project's environment, authenticated via OIDC, but this application is not integrated with it, and its intended role is storage for large files, most notably Session audio recordings, rather than for small, structured, relational data.

## Decision

We will run our own PostgreSQL 17 instance for Session-related data, deployed as a `db` service in this repository's Docker Compose setup, on the same server as the rest of the pipeline. The backend connects via `DATABASE_URL`, assembled from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` in `.env`, using the `psycopg` driver.

Large files stay out of this database and remain the Data Platform's responsibility once that integration is built. That split will get its own ADR when it is actually implemented.

## Consequences

The project operates a schema, migrations, and storage infrastructure itself instead of depending on an external API it has not integrated with, and gains full control over how Session data is read back, retained, and deleted. Because the database runs on the same server as the rest of the pipeline, it introduces no additional hosting relationship or cross-border transfer question. Nothing persists Session audio today, so any feature that needs recordings back still depends on the Data Platform integration being built.
