# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Calltrainer is an AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls (from README.md).

## Current State

Only a minimal FastAPI backend skeleton exists (`backend/app.py`, currently just a `/health` endpoint) plus Docker tooling to run it. There is no frontend, no persistence, no LLM integration, and no tests yet. `docs/arc42.md` is still mostly `TODO` — fill it in as real architecture decisions are made.

## Build / Run

- Local: `pip install -r requirements.txt`, then `uvicorn backend.app:app --reload`
- Docker: `docker compose up --build` (serves on `http://localhost:8000`)
- Docker with debugger attached (debugpy on port 5678): `docker compose -f compose.debug.yaml up --build`
- Copy `.env.example` to `.env` and fill in real values before running — `.env` is gitignored and read via `env_file` in both compose files.
- Docs site (arc42 + ADRs): `pip install -r requirements-docs.txt`, then `mkdocs serve` (serves on `http://localhost:8000`; stop the app first or pass `-a localhost:8001` to avoid a port clash). `mkdocs build` writes static output to `site/` (gitignored).

There are no lint or test commands configured yet. Add them here once they exist.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/croco22/calltrainer`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
