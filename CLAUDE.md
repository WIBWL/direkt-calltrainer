# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Calltrainer is an AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls (from README.md).

## Current State

FastAPI backend (`backend/app.py`) serves the API and, once built, the React + TypeScript frontend (`frontend/`, built with Vite; the backend serves `frontend/dist`). `/health` is a plain health check; `/api/process` takes an uploaded audio file, transcribes it, generates an in-character Persona reply, and synthesizes that reply as speech — all three steps call the same university-hosted, OpenAI-compatible `efre-direkt` endpoint, configured via a single `.env` base URL/key pair (`EFRE_URL`, `EFRE_API_KEY`) plus one model name per step (`STT_MODEL`, `LLM_MODEL`, `TTS_MODEL`). This is a spike used to validate the LLM integration, not a core Calltrainer feature (see ADR list) — expect it to be replaced by the real Session pipeline. `docs/arc42.md` is filled in. There are no tests.

**Persistence exists, but nothing in the request path uses it yet.** The schema lives in `backend/db/models.py` as twelve SQLAlchemy entities (`Persona`/`PersonaEinwand`, `Szenario`, `Sprache`, `Session`, `Turn`, `MetrikTyp`/`Messung`/`Befund`, `Feedback`/`Feedbackpunkt`, `AnalysisJob`), with `backend/db/base.py` holding the declarative base and `backend/db/session.py` the engine plus a `session_scope()` context manager — that module is the single entry point for database access. Alembic revisions live in `backend/db/migrations/`, Postgres runs as the `db` service in `compose.yaml`, and the connection string comes from `DATABASE_URL` (the `POSTGRES_*` variables configure the container itself). `models.py` is the single source of truth: both the migrations and the ER diagram are derived from it, never edited by hand.

`backend/app.py` still reads Personas, Scenarios and Languages from the hardcoded `backend/personas.py`, `backend/scenarios.py` and `backend/languages.py` — it does not import `backend.db` at all. `scripts/seed_reference_data.py` mirrors those modules into the reference tables (idempotent, safe to re-run), so the database and the hardcoded modules currently hold the same content in parallel. Switching the app over to read from the database is a deliberate later step.

## Build / Run

- Frontend: `cd frontend && npm install && npm run build` (writes to `frontend/dist`, which the backend serves) or `npm run dev` (Vite dev server on `http://localhost:5173`, calls the backend cross-origin via `VITE_API_URL`; the backend allows this origin via CORS)
- Local backend: `pip install -r requirements.txt`, then `uvicorn backend.app:app --reload`
- Docker: `docker compose up --build` (builds the frontend too, via a multi-stage Dockerfile; serves on `http://localhost:8000`)
- Copy `.env.example` to `.env` and fill in real values before running — `.env` is gitignored and read via `env_file` in the compose file (and by Vite, via `envDir` pointing at the repo root).
- Testing without a real `EFRE_API_KEY`: run `python scripts/mock_llm_server.py`, then start the app with `EFRE_URL` pointed at it (`http://localhost:9000` locally, `http://host.docker.internal:9000` from inside a container). The mock returns fixed transcript/reply/audio values for all three pipeline steps.
- Database: `docker compose up -d db` starts Postgres on 5432. Then `alembic upgrade head` applies the migrations and `python scripts/seed_reference_data.py` fills the reference tables. Both read `DATABASE_URL` from `.env`; the seed script calls `load_dotenv()` itself, `backend/db/session.py` does not.
- Schema changes: edit `backend/db/models.py`, then `alembic revision --autogenerate -m "..."`. **Always read the generated migration before applying it** — autogenerate adds `NOT NULL` columns without backfilling, which fails on non-empty tables, and it leaves unique constraints unnamed, which makes `downgrade()` unrunnable. The ER diagram is regenerated automatically on every docs build (see below); `python scripts/generate_erd.py` refreshes `docs/er_modell.png`/`.svg` on demand and needs the Graphviz `dot` binary (`brew install graphviz`).
- Docs site (arc42 + ADRs): `pip install -r requirements.txt`, then `mkdocs serve` (serves on `http://localhost:8000`; stop the app first or pass `-a localhost:8001` to avoid a port clash). `mkdocs build` writes static output to `site/` (gitignored). There is no separate requirements file for docs or dev tooling — `requirements.txt` carries everything.

There are no lint or test commands configured yet. Add them here once they exist.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/croco22/calltrainer`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
