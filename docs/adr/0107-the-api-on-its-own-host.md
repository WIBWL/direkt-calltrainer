# ADR 0107: The API on Its Own Host, Behind CORS

## Context

The deployment follows the infrastructure repository's convention: one Traefik router per service, each on its own host.

## Decision

- The SPA is `calltrainer.efre-direkt.de`, the API `calltrainer-backend.efre-direkt.de`.
- The backend installs `CORSMiddleware` from `CORS_ORIGINS`, authorised by the `Authorization` header only (no credentials), exposing `Content-Disposition`. Unset, nothing is installed.
- The SPA reads `apiUrl` from `/config.js` at runtime and prefixes every request and the socket URL with it.
- Locally, Vite proxies `/api`, `/ws` and `/health`, so there is one origin.
- The WebSocket has no origin check: the token rides in the first message, so another origin has no credentials to borrow.

## Consequences

Every authorised request has a preflight, cached ten minutes. A response header the SPA reads must be in `expose_headers`. Security headers are a Traefik middleware; the CSP is the frontend image's own (ADR 0109).
