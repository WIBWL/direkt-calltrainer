# ADR 0020: Deployment on a University-Hosted Server

## Status

Accepted

## Context

arc42's Verteilungssicht is still open. Beyond local Docker Compose, the running system needs an actual host for the pilot with Solox GmbH. Options considered would have included a commercial cloud provider or infrastructure provided by Solox itself.

## Decision

We will deploy the application on a server hosted by the university, alongside the EFRE-Direkt gateway (ADR 0011).

## Consequences

Consistent with EFRE-Direkt already being university infrastructure — one hosting relationship to manage instead of two, and no commercial cloud cost. The project depends on the university's server for uptime and maintenance, outside the team's direct control. Concrete deployment details (server access, CI/CD, domain and TLS setup) are not yet decided.
