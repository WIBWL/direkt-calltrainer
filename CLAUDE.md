# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Calltrainer is an AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls (from README.md).

## Current State

FastAPI backend (`backend/app.py`) serves the API and, once built, the React + TypeScript frontend (`frontend/`, built with Vite; the backend serves `frontend/dist`). `/health` is a plain health check; `/api/process` takes an uploaded audio file, transcribes it, translates the transcript to English, and synthesizes speech from the translation — all three steps call the university-hosted, OpenAI-compatible `efre-direkt` LLM endpoint configured via `.env` (`LLM_URL`, `LLM_API_KEY`, `STT_MODEL`, `LLM_MODEL`, `TTS_MODEL`; see ADR 0011). This audio-translate flow is a throwaway spike used to validate the LLM integration, not a core Calltrainer feature (see ADR list) — expect it to be replaced by the real Session pipeline. There is still no persistence in this backend (Session/document data is meant to go to an external Datenplattform, see ADR 0010) and no tests. `docs/arc42.md` is filled in.

## Build / Run

- Frontend: `cd frontend && npm install && npm run build` (writes to `frontend/dist`, which the backend serves) or `npm run dev` (Vite dev server on `http://localhost:5173`, calls the backend cross-origin via `VITE_API_URL`; the backend allows this origin via CORS)
- Local backend: `pip install -r requirements.txt`, then `uvicorn backend.app:app --reload`
- Docker: `docker compose up --build` (builds the frontend too, via a multi-stage Dockerfile; serves on `http://localhost:8000`)
- Copy `.env.example` to `.env` and fill in real values before running — `.env` is gitignored and read via `env_file` in the compose file (and by Vite, via `envDir` pointing at the repo root).
- Testing without a real `LLM_API_KEY`: run `python scripts/mock_llm_server.py`, then start the app with `LLM_URL` pointed at it (`http://localhost:9000` locally, `http://host.docker.internal:9000` from inside a container). The mock returns fixed transcript/translation/audio values for all three pipeline steps.
- Docs site (arc42 + ADRs): `pip install -r requirements-docs.txt`, then `mkdocs serve` (serves on `http://localhost:8000`; stop the app first or pass `-a localhost:8001` to avoid a port clash). `mkdocs build` writes static output to `site/` (gitignored).

There are no lint or test commands configured yet. Add them here once they exist.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/croco22/calltrainer`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
