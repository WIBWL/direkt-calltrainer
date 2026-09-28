# ADR 0108: Three Packages, One Dockerfile, Deployed From the Infrastructure Repository

## Status

Accepted (amends ADR 0104; the deployment part of ADR 0020 was already superseded in practice)

## Context

ADR 0104 split the images, but not the code: the worker image ran `backend/` whole, with the API, auth, STT and TTS it never uses, installed the backend's `requirements.txt`, and needed every pipeline variable because `backend/clients/config.py` read them all at import. The API imported the wrap-up generator too, only to hand RQ a function object. Three Dockerfiles, a `docker-bake.hcl` and a `compose.prod.yaml` sat in this repository, and the root held a dozen files that each served one tool. The dataplatform, deployed to the same host, does it differently: one root `Dockerfile` with a target per image, a workspace of packages with one lockfile, `scripts/build-and-push.sh` tagging from git for WUD, `dev-compose.yaml` with the backing services only, and the deployment in `direkt-infrastructure`.

## Decision

**Three Python packages**, a uv workspace with one `uv.lock`:

* `shared/` — what both processes import: the database (models, session, seed data, migrations), the gateway client and LLM, the measuring code, the job status and queue, the Turn timeline, logging, settings.
* `backend/` — the API, the live call, provisioning, the scripts.
* `worker/` — the entry point and the wrap-up generator.

`shared` imports neither of the others, and `backend` and `worker` never import each other; the backend queues the job by its dotted name. `backend/tests/test_module_dependencies.py` pins both, statically and by what each process actually loads. Each package's `pyproject.toml` lists what it imports; they are virtual members (imported from the repository root, `/app` in the images), not installed wheels. Tests sit beside each package; the fixtures they share are `shared/tests/fixtures.py`.

**One root `Dockerfile`**, targets `frontend`, `backend`, `worker`. Each Python image installs its own package's closure (`uv sync --locked --package ...`) and copies `shared/` plus its own package, nothing else. `scripts/build-and-push.sh` (the dataplatform's, with these three names) pushes `calltrainer-{frontend,backend,worker}` as the pushed `v*` git tag on HEAD and as `latest`, with provenance, so WUD can follow the digest.

**Local development** runs the apps on the host against `dev-compose.yaml` (Postgres, Redis, Keycloak only); the frontend is served by Vite, which proxies the API. There is no compose file that builds or runs the apps.

**Deployment** is `direkt-infrastructure/public/calltrainer/compose.yml`, not this repository.

**The root** holds only what the whole repository shares: `Dockerfile`, `dev-compose.yaml`, `pyproject.toml`/`uv.lock`/`.python-version` (with the pytest, flake8 and pylint configuration), `.env.example`, `keycloak/`, `scripts/build-and-push.sh`, the docs.

## Consequences

The worker image carries no FastAPI, KugelAudio or pypdf and needs only the gateway, database and queue settings. A dependency declared in the wrong package fails in that image, not on a developer's machine, where `uv sync` installs everything. `alembic` runs as `uv run alembic -c shared/db/alembic.ini`, and a script as `python -m backend.scripts.<name>`.

A release is a pushed tag plus `scripts/build-and-push.sh`; WUD rolls it out within the hour, which makes the pre-deployment `pg_dump` a step before the push, not before an `up`. A configuration change to the deployment is a commit to `direkt-infrastructure`.

The call cannot be tried under `npm run dev` (Silero VAD, see CLAUDE.md); `npm run build:watch` with `npm run preview` is the local path for it.
