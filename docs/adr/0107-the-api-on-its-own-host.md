# ADR 0107: The API on Its Own Host, Behind CORS

## Status

Accepted (supersedes the single-origin part of ADR 0104)

## Context

ADR 0104 kept the browser on one origin: the frontend container (locally) or an external proxy (deployed) routed `/api`, `/ws` and `/health` to the backend, so there was no CORS middleware. The deployment now lives in `direkt-infrastructure` beside the dataplatform, whose convention is one Traefik router per service, each on its own host under `efre-direkt.de`, with the backend allowing the SPA's origin.

## Decision

* The SPA is `calltrainer.efre-direkt.de`, the backend `calltrainer-backend.efre-direkt.de` (the worker has no host).
* The backend installs FastAPI's `CORSMiddleware` from `CORS_ORIGINS` (`backend/cors.py`): comma-separated origins or `*`, authorised by the `Authorization` header only (no cookies, so no credentials), `Content-Disposition` exposed for the data export. Unset, nothing is installed — the dataplatform's rule, and the development setup.
* The frontend reads the backend's origin at runtime as `apiUrl` from `/config.js` (`API_URL` in the container, `src/config.ts`); every request is prefixed with it and the call's WebSocket URL is derived from it. Empty means the SPA's own origin.
* In development Vite proxies `/api`, `/ws` and `/health` to the backend on the host, so the browser still sees one origin and no CORS is involved.
* The frontend image serves the SPA only; its nginx no longer knows the backend.

The WebSocket gets no origin check. A browser sends no preflight for one, but the token rides in the first message rather than a cookie, so a page on another origin has no credentials to borrow.

## Consequences

Every authorised request from the SPA is preceded by a preflight, cached for ten minutes (`max_age`). A route that sets a response header the SPA must read has to be added to `expose_headers`. The Keycloak client's web origins are unchanged: the SPA's origin is the one that talks to Keycloak. The security headers the external proxy set (HSTS, `nosniff`, `Referrer-Policy`, `Permissions-Policy: microphone=(self)`) are a Traefik middleware in `direkt-infrastructure/public/calltrainer/compose.yml`.
