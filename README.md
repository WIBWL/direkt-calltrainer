# EFRE-DiReKT Calltrainer

AI-powered phone conversation trainer with real-time speech analysis and behavioral feedback.

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/status-active--development-yellow)

## About

Calltrainer is a use case built within [EFRE-DiReKT](https://efre-direkt.de/), an applied-AI research project at the University of Würzburg's Chair for Business Administration and Business Informatics, funded by the Bavarian Ministry of Science through the EU's European Regional Development Fund. Users practice phone calls against an AI counterpart (a Persona, picked from an extensible library) in a configurable Scenario, then get qualitative feedback on how they communicated, e.g. clarity, tone, structure.

## Architecture

FastAPI backend, React + TypeScript frontend, one Docker image. Speech-to-text, dialogue generation, and text-to-speech all run through a university-hosted, OpenAI-compatible model gateway - no separate provider accounts or local models needed to run the app.

> **Note:** The EFRE-DiReKT gateway is only reachable from within the University of Würzburg network - connect via campus network or VPN before running the app.

## 1. Setup

Copy `.env.example` to `.env` and fill in the real `EFRE_API_KEY`.

## 2. Run the App

```powershell
docker compose up --build
```

Builds the frontend too (multi-stage Dockerfile) and serves everything on `http://localhost:8000`.

For development, add `--watch` (`docker compose up --build --watch`) to have the container pick up code changes automatically: backend edits are synced in and the app restarts without a full rebuild, while frontend edits and `requirements.txt` changes trigger a rebuild.

## 3. Documentation

The full architecture documentation - arc42 and every Architecture Decision Record (ADR) - is served via [MkDocs](https://www.mkdocs.org):

```powershell
pip install -r requirements-docs.txt
mkdocs serve
```

> Also runs on port 8000 by default - stop the app first, or use `mkdocs serve -a localhost:8001` to avoid the port clash.
