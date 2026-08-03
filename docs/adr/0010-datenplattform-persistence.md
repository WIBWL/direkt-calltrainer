# ADR 0010: Persistence Delegated to an External Datenplattform

## Status

Accepted

## Context

The product needs to store uploaded documents and Session information somewhere. A separately hosted "Datenplattform" service already exists for this purpose, external to this repository's deployment.

## Decision

We will not run our own database for uploaded documents or Session data. The backend forwards this data, together with the user's auth token, to the external Datenplattform service, which is itself authenticated via OIDC.

## Consequences

No database schema, migrations, or storage infrastructure to operate ourselves. In exchange, the project has a hard dependency on the Datenplattform's availability and API, and its specifics are not yet documented in this repo (`DATENPLATTFORM_URL` is still a placeholder).
