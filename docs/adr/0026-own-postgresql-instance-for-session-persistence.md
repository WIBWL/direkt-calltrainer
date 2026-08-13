# ADR 0026: Own PostgreSQL Instance for Session Persistence (Supersedes ADR 0010)

## Status

Proposed

## Context

ADR 0010 decided to delegate all Session/document persistence to an external Datenplattform, keeping this repository free of its own database. ADR 0024 separately decided that, once persistence is introduced beyond the MVP, Session data would still be written to that same Datenplattform, hosted alongside the rest of the pipeline (ADR 0021). The Datenplattform itself already exists as a service, but this application is not yet integrated with it — `DATENPLATTFORM_URL` is still a placeholder (ADR 0010) — and its intended role going forward is storage for large files (e.g. audio recordings), not for the kind of small, structured, relational data this schema captures (Session metadata, Turn text, Feedback, etc.). So when the first real persistence layer for Session data was implemented, it was built directly against a self-hosted PostgreSQL database instead: a `db` service added to `compose.yaml`, `DATABASE_URL`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` added to `.env.example`, and a `psycopg` driver added to `requirements.txt`.

## Decision

For Session-related data (Persona, Szenario, Sprache, Session, Turn, Messung, Befund, Feedback, Feedbackpunkt, AnalysisJob), we supersede ADR 0010. We will run our own PostgreSQL 17 instance, deployed as a `db` service in this repository's Docker Compose setup on the same university-hosted server as the rest of the pipeline (ADR 0021), rather than forwarding this data to an external Datenplattform. The backend connects via `DATABASE_URL`, assembled from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` in `.env`.

## Consequences

We now own a schema, migrations, and storage infrastructure ourselves — precisely the operational burden ADR 0010 chose to avoid — in exchange for not depending on an external API this application hasn't integrated with yet. Because the database is provisioned on the same university-hosted server as the EFRE-Direkt gateway and application server (ADR 0021), this does not introduce a new hosting relationship or cross-border transfer question beyond what ADR 0021 already established, and ADR 0024's consent-gated, self-service-deletion model for post-MVP persistence still applies — just against a database this project operates directly rather than a delete capability someone else was going to build.

This does not remove the Datenplattform from the picture: it is expected to still be connected for large files, most notably Session audio recordings, once that integration is built — this schema does not persist audio anywhere today. That split (structured data in our own Postgres, large files in the Datenplattform) is not yet the subject of its own ADR and should get one once the Datenplattform integration is actually implemented.
