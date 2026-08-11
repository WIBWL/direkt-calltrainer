# EFRE-DiReKT Calltrainer

AI-powered phone conversation trainer with real-time speech analysis and behavioral feedback.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/status-active--development-yellow)

## About

Calltrainer is a use case built within [EFRE-DiReKT](https://www.wiwi.uni-wuerzburg.de/wibwl/forschungsprojekte/efre-direkt/), an applied-AI research project at the University of Würzburg's Chair for Business Administration and Business Informatics (WIBWL), funded by the Bavarian Ministry of Science through the EU's European Regional Development Fund. Users practice phone calls against an AI counterpart (a Persona, picked from an extensible library) in a configurable Scenario, then get qualitative feedback on how they communicated, e.g. clarity, tone, structure.

## Architecture

FastAPI backend, React + TypeScript frontend, one Docker image. Speech-to-text, dialogue generation, and text-to-speech all run through [EFRE-DiReKT](https://efre-direkt.de/), a university-hosted, OpenAI-compatible model gateway - no separate provider accounts or local models needed to run the app.

## Prerequisites

| Requirement | Notes |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Includes Docker Compose |
| `EFRE_API_KEY` | Access key for the EFRE-DiReKT gateway |

## 1. Setup

Copy `.env.example` to `.env` and fill in the real `EFRE_API_KEY`.

## 2. Run the App

```powershell
docker compose up --build
```

Builds the frontend too (multi-stage Dockerfile) and serves everything on `http://localhost:8000`.

## 3. Documentation

The full architecture documentation - arc42 and every Architecture Decision Record (ADR) - is served via [MkDocs](https://www.mkdocs.org):

```powershell
mkdocs serve
```

> Also runs on port 8000 by default - stop the app first, or use `mkdocs serve -a localhost:8001` to avoid the port clash.

## 4. Testing without a real API-Key

If no valid `EFRE_API_KEY` is available, or the EFRE-DiReKT server has some other model-provisioning problem, the pipeline can be tested against a local mock server instead.

**Terminal 1:**

```powershell
python scripts/mock_llm_server.py
```

**Terminal 2:**

```powershell
$env:EFRE_URL = "http://localhost:9000"
uvicorn backend.app:app --reload
```

This runs only the API on `http://localhost:8000`. For the full UI, also run `npm run dev` in `frontend/` and open `http://localhost:5173`.

> **Note:** Once real credentials are back in `.env`, unset `$env:EFRE_URL` - otherwise it keeps overriding `.env` and pointing the app at the mock server, which likely isn't running anymore.
