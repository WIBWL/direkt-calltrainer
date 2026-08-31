# ADR 0010: Own PostgreSQL Instance for Session Persistence

## Status

Accepted

## Context

The product needs a durable store for Session data — Session metadata, Turn text, speech-analysis results, Feedback, and the Session audio itself. An external Data Platform service exists in the project's environment, authenticated via OIDC, but this application is not integrated with it, and its role is to move data, not to retain it: it is a transport channel, so nothing the product needs to keep can live there.

## Decision

We will run our own PostgreSQL 17 instance for Session-related data, deployed as a `db` service in this repository's Docker Compose setup, on the same server as the rest of the pipeline. The backend connects via `DATABASE_URL`, assembled from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` in `.env`, using the `psycopg` driver.

Everything the product persists lives in this database, large files such as Session audio recordings included. There is no second store to split data across.

## Consequences

The project operates a schema, migrations, and storage infrastructure itself instead of depending on an external API it has not integrated with, and gains full control over how Session data is read back, retained, and deleted. Because the database runs on the same server as the rest of the pipeline, it introduces no additional hosting relationship or cross-border transfer question. Holding large binary data in Postgres alongside the relational rows keeps the storage story to a single system, at the cost of database size and backup volume growing with call volume.
