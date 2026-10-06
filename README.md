# EFRE-DiReKT Calltrainer

An AI phone conversation trainer with speech analysis and behavioural feedback, built within [EFRE-DiReKT](https://efre-direkt.de/) at the University of Würzburg. Users practise calls against an AI Persona in a Scenario, then get qualitative feedback and measured statistics.

The frontend is React + TypeScript. Behind it are two Python processes, the FastAPI backend and the wrap-up worker, in one uv workspace of three packages (`shared/`, `backend/`, `worker/`), built as three images from one `Dockerfile`. STT and the LLM run on the DiReKT gateway, which needs the VPN. TTS runs on KugelAudio.

## Setup

You need [uv](https://docs.astral.sh/uv/), Node 22 and Docker. Use Python **3.12**: on 3.14, SQLAlchemy 2.0.36 fails with a `TypeError` that looks like a broken model.

```sh
uv sync
(cd frontend && npm install)
cp .env.example .env                          # fill in DIREKT_API_KEY and KUGELAUDIO_API_KEY
docker compose -f dev-compose.yaml up -d      # Postgres :15433, Redis :16379, Keycloak :18081
```

Every variable in `.env.example` is required; any can instead be given as `NAME_FILE=/path`. Run `source .env` in every shell that starts a process. The `export`s matter.

## Run

```sh
uv run uvicorn backend.app:app --reload       # backend :8000; migrates and seeds on startup
uv run python -m worker                       # wrap-up worker
cd frontend && npm run dev                    # SPA :5173, everything except the call
cd frontend && npm run build:watch            # with `npm run preview` in a second shell: SPA :8391
```

The call's voice detection (Silero VAD, onnxruntime-web) does not load under `npm run dev`, so use the production build for anything involving the call. Both Vite servers proxy `/api`, `/ws` and `/health` to `:8000`. Restart Vite after changing `.env`. The worker needs `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` on macOS (already set in `.env.example`) and does not run on Windows. If the worker is down, calls still work and wrap-ups queue.

## Login

The dev Keycloak at `http://localhost:18081` imports `keycloak/direkt-realm.json`. The password equals the username. Admin console: `admin`/`admin`.

| user | role `calltrainer-user` | Organization |
|---|---|---|
| `alice`, `bob` | yes | `company-a` |
| `carol` | yes | `company-b` |
| `dave` | no | none (sees "nicht freigeschaltet") |

To change the realm, edit the JSON and drop the volume:

```sh
docker compose -f dev-compose.yaml rm -sf keycloak && docker volume rm direkt-calltrainer-keycloak-data
```

## Test and lint

```sh
source .env && uv run pytest                  # DB tests need dev-compose's Postgres; check the skip count
uv run flake8 && uv run pylint backend/ shared/ worker/
(cd frontend && npm run lint && npm test)
```

## Schema changes

```sh
uv run alembic -c shared/db/alembic.ini revision --autogenerate -m "..."
```

Read every generated migration before applying it. Autogenerate adds `NOT NULL` columns without backfilling them, turns renames into a drop plus a create, and misses `CHECK` constraints.

## Scripts

Run them as `uv run python -m backend.scripts.<name>` locally, or `docker compose exec calltrainer-backend python -m backend.scripts.<name>` on the server.

- `check_backends`: one real request each to STT, LLM and TTS
- `requeue_feedback [--apply]`: re-queue stored Sessions without a wrap-up
- `apply_retention [--apply]`: list or delete Sessions past six months
- `inspect_pressure_segments`: check how wrap-ups marked demanding stretches
- `stress_db`: load-test the schema on a throwaway database
- `seed_reference_data`: migrate and seed by hand
- `generate_erd`: draw the ER diagram (needs Graphviz)
- `play_scenarios`, `scenario_probes`, `try_voice`: prompt and voice experiments

## Release

Push a `v*` tag, then run `scripts/build-and-push.sh [frontend backend worker]` (needs bash 4). The deployment lives in `direkt-infrastructure`; see [docs/deployment.md](docs/deployment.md).

## Docs

`uv run mkdocs serve -a localhost:8001` serves arc42 and the ADRs.
