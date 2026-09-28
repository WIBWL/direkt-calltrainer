# EFRE-DiReKT Calltrainer

AI-powered phone conversation trainer with real-time speech analysis and behavioral feedback.

![Status](https://img.shields.io/badge/status-active--development-yellow)

## About

Calltrainer is a use case built within [EFRE-DiReKT](https://efre-direkt.de/), an applied-AI research project at the University of Würzburg's Chair for Business Administration and Business Informatics, funded by the Bavarian Ministry of Science through the EU's European Regional Development Fund. Users practice phone calls against an AI counterpart (a Persona, picked from an extensible library) in a configurable Scenario, then get qualitative feedback on how they communicated, e.g. clarity, tone, structure.

## Architecture

A React + TypeScript frontend and two Python processes — the FastAPI backend (the API and the live call) and the wrap-up worker — built as three images from one `Dockerfile`. The Python side is one uv workspace of three packages: `shared/`, `backend/`, `worker/` (ADR 0108). Speech-to-text and dialogue generation run through the EFRE-DiReKT gateway — an OpenAI-compatible endpoint, named with one model per step in `.env`. Text-to-speech runs on KugelAudio. One backend per leg, no fallbacks and no switches between them (ADR 0103). No local models are needed.

> **Note:** The EFRE-DiReKT gateway is only reachable from its own network - connect via VPN before running the app.

## Running it locally

The apps run on your machine; Docker runs only Postgres, Redis and Keycloak. You need [uv](https://docs.astral.sh/uv/), Node 22 and Docker.

```sh
uv sync                                       # Python 3.12 and every package, plus the dev tools
(cd frontend && npm install)
cp .env.example .env                          # then fill in DIREKT_API_KEY and KUGELAUDIO_API_KEY
docker compose -f dev-compose.yaml up -d      # Postgres :15433, Redis :16379, Keycloak :18081
```

Then, each in its own shell with `source .env` first:

```sh
uv run uvicorn backend.app:app --reload       # the backend, :8000
uv run python -m worker                       # the wrap-up worker
cd frontend && npm run dev                    # the SPA on http://localhost:5173
```

The live call needs the production build — voice detection does not load under `npm run dev` — so for anything touching the call run `npm run build:watch` and `npm run preview` instead, and open `http://localhost:8391`. Both Vite servers forward `/api`, `/ws` and `/health` to the backend.

## Login (Keycloak)

`dev-compose.yaml` brings its own Keycloak on `http://localhost:18081` and imports `keycloak/direkt-realm.json` — the `direkt-calltrainer` client and three fixed users:

| user | password | company (`tenant`) |
|---|---|---|
| `niklas` | `niklas` | Solox |
| `mathias` | `mathias` | Solox |
| `eberhard` | `eberhard` | APPOLLO |

Opening the app redirects to Keycloak; log in as any of them. There is nothing to configure and no roles — a valid token is all the app checks (ADR 0009).

**To change the realm, edit the JSON and drop Keycloak's volume** — import is skipped for a realm that already exists:

```sh
docker compose -f dev-compose.yaml rm -sf keycloak && docker volume rm direkt-calltrainer-keycloak-data
docker compose -f dev-compose.yaml up -d
```

The Keycloak admin console is at <http://localhost:18081> with `admin` / `admin`. Production uses the shared `direkt` realm at `keycloak.efre-direkt.de`, administered by hand (the import file is dev-only).

## Tests

```sh
source .env && uv run pytest                  # needs dev-compose.yaml's Postgres, or the database tests skip
uv run flake8 && uv run pylint backend/ shared/ worker/
(cd frontend && npm run lint && npm test)
```

## Images and deployment

`scripts/build-and-push.sh` builds the three images for `registry.internal.efre-direkt.de` from a commit with a pushed `v*` tag. The deployment itself is in `direkt-infrastructure` (`public/calltrainer/compose.yml`), which updates to a new `latest` on its own; see `docs/deployment.md`.

## Documentation

The full architecture documentation - arc42 and every Architecture Decision Record (ADR) - is served via [MkDocs](https://www.mkdocs.org):

```sh
uv run mkdocs serve -a localhost:8001
```
