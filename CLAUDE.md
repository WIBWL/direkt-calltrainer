# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Calltrainer is an AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls (from README.md).

## Current State

FastAPI backend (`backend/app.py`) serves the API and, once built, the React + TypeScript frontend (`frontend/`, built with Vite; the backend serves `frontend/dist`). `/health` is a plain health check; `/api/personas` and `/api/scenarios` list the Persona/Scenario options shown before a Session starts — any Persona can run any Scenario, no compatibility to filter by. There is no Language selection: each Persona has exactly one fixed Language/voice (`backend/personas.py`), and only German is supported for now (English support was removed, not just hidden — re-introducing it means giving the relevant Personas their own `language_id`/`language_name`/voice, not a shared global setting). The live Session itself runs over a per-Session WebSocket at `/ws/session` (`backend/api/session_ws.py`): the client streams one full Turn of recorded audio at a time (browser-side voice-activity detection ends each Turn automatically, no manual button), the server runs it through STT → streamed dialogue generation → chunked TTS (`backend/session/orchestrator.py`, `backend/clients/`), and streams synthesized audio back chunk-by-chunk so playback can start before the full reply is done generating (ADR 0026, which supersedes ADR 0013's non-streaming pipeline). All three steps call the same university-hosted, OpenAI-compatible `efre-direkt` endpoint, configured via a single `.env` base URL/key pair (`EFRE_URL`, `EFRE_API_KEY`) plus one model name per step (`STT_MODEL`, `LLM_MODEL`, `TTS_MODEL`). No text is shown during the live call, only a state animation (listening/thinking/speaking) — the full Transcript is sent once, at the end, and shown as a post-call summary. Persistence lives in `backend/db/` but it isn't integrated into `backend/app.py` yet. `backend/db/models.py` holds the SQLAlchemy schema, `backend/db/session.py` the `session_scope()` context manager used for all database access, and `backend/db/migrations/` the Alembic revisions; Postgres runs as the `db` service in `compose.yaml` (ADR 0010). The migrations and the ER diagram in `docs/datenmodell.md` are generated from `backend/db/models.py`, not edited by hand. The schema's rationale is in the persistence ADRs 0025 through 0032. There is no AI-generated Feedback (ADR 0004/0015/0019/0020's async worker is not built), and there are no tests yet. `docs/arc42.md` is filled in.

## Build / Run

- Frontend: `cd frontend && npm install && npm run build` (writes to `frontend/dist`, which the backend serves) or `npm run dev` (Vite dev server on `http://localhost:5173`, calls the backend cross-origin via `VITE_API_URL`; the backend allows this origin via CORS)
- Turn-taking uses Silero VAD in-browser (`@ricky0123/vad-web` + `onnxruntime-web`, ONNX+WASM); `npm run dev`/`npm run build`'s `predev`/`prebuild` hooks (`frontend/scripts/copy-vad-assets.mjs`) copy its ~15MB of runtime assets into `frontend/public/vad/` (gitignored, regenerated on every dev/build run — not tied to `npm install`, since the Docker build's `npm ci` layer runs before the rest of the source, including this script, is even copied into the image). Known gap: this currently fails under `npm run dev` specifically — Vite 5's dev-server import-analysis 500s on onnxruntime-web's dynamically-imported `.mjs` WASM glue (a dev-only Vite/onnxruntime-web interaction, unresolved so far). The production build (`npm run build`, served by the backend) is unaffected — use that path when testing VAD/turn-taking changes.
- Local backend: `uvicorn backend.app:app --reload`
- Docker: `docker compose up --build` (builds the frontend too, via a multi-stage Dockerfile; serves on `http://localhost:8000`)
- Copy `.env.example` to `.env` and fill in real values before running — `.env` is gitignored and read via `env_file` in the compose file (and by Vite, via `envDir` pointing at the repo root).
- Testing without a real `EFRE_API_KEY`: run `python scripts/mock_llm_server.py`, then start the app with `EFRE_URL` pointed at it (`http://localhost:9000` locally, `http://host.docker.internal:9000` from inside a container). The mock returns fixed transcript/reply/audio values for all three pipeline steps.
- Database: `docker compose up -d db` starts Postgres on 5432. Then `alembic upgrade head` applies the migrations and `python scripts/seed_reference_data.py` fills the reference tables. Both read `DATABASE_URL` from `.env` and call `load_dotenv()` themselves; `backend/db/session.py` does not — it reads `DATABASE_URL` lazily, on the first call to `session_scope()`/`get_engine()`, so importing it never requires an environment. The `DATABASE_URL` in `.env` points at `localhost` for these host-side calls; the app container gets its own URL pointing at the `db` host, set in `compose.yaml`.
- Schema changes: edit `backend/db/models.py`, then `alembic revision --autogenerate -m "..."`. **Always read the generated migration before applying it** — autogenerate adds `NOT NULL` columns without backfilling, which fails on non-empty tables, and it leaves unique constraints unnamed, which makes `downgrade()` unrunnable. The ER diagram is regenerated automatically on every docs build (see below); `python scripts/generate_erd.py` refreshes `docs/er_modell.png`/`.svg` on demand and needs the Graphviz `dot` binary (`brew install graphviz`).
- Docs site (arc42 + ADRs): `mkdocs serve` (serves on `http://localhost:8000`; stop the app first or pass `-a localhost:8001` to avoid a port clash). `mkdocs build` writes static output to `site/` (gitignored).

There are no lint or test commands configured yet. Add them here once they exist.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/croco22/calltrainer`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
