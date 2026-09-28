# ADR 0104: Frontend, Backend and Worker as Three Images

## Status

Accepted (amends ADR 0008)

## Context

One multi-stage `Dockerfile` built the SPA with Node and copied it into the Python image, which served it through a `StaticFiles` subclass in `backend/app.py`. The worker ran the same image with a different command. So a frontend change rebuilt and restarted the backend, and the backend and worker images carried each other's concerns (the SPA, and in the worker's case a whole web app it never served).

## Decision

Three images, three services:

* **frontend** (`frontend/Dockerfile`, context `frontend/`): Vite builds the SPA, Caddy serves it. Its `Caddyfile` forwards `/api*`, `/ws*` and `/health*` to `backend:8000`, falls back to `index.html` for client routes, and keeps a missing path whose last segment has a dot a 404. It is the only service that publishes a port (`8391` locally).
* **backend** (`backend/Dockerfile`, context the repository root): gunicorn/uvicorn with the API and the live session; no published port, no static files.
* **worker** (`backend/worker.Dockerfile`, same context): the same code and dependencies, `python -m backend.worker`.

The browser still sees one origin, so there is still no CORS middleware, and Keycloak still redirects back to that origin.

In deployment the repository ships no reverse proxy: the services sit behind an external one that terminates TLS and routes `/api*`, `/ws*` and `/health*` to the backend itself. `compose.prod.yaml` publishes no port, joins the frontend and backend to that proxy's network (`PROXY_NETWORK`, aliases `calltrainer-frontend`/`calltrainer-backend`), and runs the frontend with `static.Caddyfile`, which serves the SPA only and answers a backend path with 404. Both Caddyfiles import the static rules from `spa.caddy`. What the external proxy must do is in `docs/deployment.md`.

## Consequences

The SPA's fallback rules now live in `frontend/spa.caddy`, not in Python, and no pytest covers them; `tests/test_spa_routing.py` went with `SinglePageApp`. A change to those rules has to be checked against a running `docker compose up`.

The backend and worker Dockerfiles are nearly identical on purpose; the Python pin and `requirements.txt` have to move in both together. The compose service `app` is now `backend`, so `docker compose exec backend ...` runs the scripts.
