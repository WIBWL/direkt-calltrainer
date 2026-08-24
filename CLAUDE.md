# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Calltrainer is an AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls (from README.md).

## Current State

FastAPI backend (`backend/app.py`) serves the API and, once built, the React + TypeScript frontend (`frontend/`, built with Vite; the backend serves `frontend/dist`). `/health` is a plain health check; `/api/personas` and `/api/scenarios` list the Persona/Scenario options shown before a Session starts — any Persona can run any Scenario, no compatibility to filter by. There is no Language selection: each Persona has exactly one fixed Language/voice (`backend/personas.py`), and only German is supported for now (English support was removed, not just hidden — re-introducing it means giving the relevant Personas their own `language_id`/`language_name`/voice, not a shared global setting). The live Session itself runs over a per-Session WebSocket at `/ws/session` (`backend/api/session_ws.py`): the client streams one full Turn of recorded audio at a time (browser-side voice-activity detection ends each Turn automatically, no manual button), the server runs it through STT → streamed dialogue generation → chunked TTS (`backend/session/orchestrator.py`, `backend/clients/`), and streams synthesized audio back chunk-by-chunk so playback can start before the full reply is done generating (ADR 0026, which supersedes ADR 0013's non-streaming pipeline). All three steps call the same university-hosted, OpenAI-compatible `efre-direkt` endpoint, configured via a single `.env` base URL/key pair (`EFRE_URL`, `EFRE_API_KEY`) plus one model name per step (`STT_MODEL`, `LLM_MODEL`, `TTS_MODEL`). No text is shown during the live call, only a state animation (listening/thinking/speaking) — the full Transcript is sent once, at the end, and shown as a post-call summary. There is still no persistence in this backend (Session/document data is meant to go to an external Datenplattform, see ADR 0010), no AI-generated Feedback (ADR 0004/0015/0019/0020's async worker is not built), and no tests. `docs/arc42.md` is filled in.

## Build / Run

- Frontend: `cd frontend && npm install && npm run build` (writes to `frontend/dist`, which the backend serves) or `npm run dev` (Vite dev server on `http://localhost:5173`, calls the backend cross-origin via `VITE_API_URL`; the backend allows this origin via CORS)
- Turn-taking uses Silero VAD in-browser (`@ricky0123/vad-web` + `onnxruntime-web`, ONNX+WASM); `npm run dev`/`npm run build`'s `predev`/`prebuild` hooks (`frontend/scripts/copy-vad-assets.mjs`) copy its ~15MB of runtime assets into `frontend/public/vad/` (gitignored, regenerated on every dev/build run — not tied to `npm install`, since the Docker build's `npm ci` layer runs before the rest of the source, including this script, is even copied into the image). Known gap: this currently fails under `npm run dev` specifically — Vite 5's dev-server import-analysis 500s on onnxruntime-web's dynamically-imported `.mjs` WASM glue (a dev-only Vite/onnxruntime-web interaction, unresolved so far). The production build (`npm run build`, served by the backend) is unaffected — use that path when testing VAD/turn-taking changes.
- Local backend: `pip install -r requirements.txt`, then `uvicorn backend.app:app --reload`
- Docker: `docker compose up --build` (builds the frontend too, via a multi-stage Dockerfile; serves on `http://localhost:8000`)
- Copy `.env.example` to `.env` and fill in real values before running — `.env` is gitignored and read via `env_file` in the compose file (and by Vite, via `envDir` pointing at the repo root).
- Testing without a real `EFRE_API_KEY`: run `python scripts/mock_llm_server.py`, then start the app with `EFRE_URL` pointed at it (`http://localhost:9000` locally, `http://host.docker.internal:9000` from inside a container). The mock returns fixed transcript/reply/audio values for all three pipeline steps.
- Docs site (arc42 + ADRs): `pip install -r requirements-docs.txt`, then `mkdocs serve` (serves on `http://localhost:8000`; stop the app first or pass `-a localhost:8001` to avoid a port clash). `mkdocs build` writes static output to `site/` (gitignored).

There are no lint or test commands configured yet. Add them here once they exist.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/croco22/calltrainer`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
