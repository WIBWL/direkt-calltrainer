# ADR 0108: Three Packages, Three Images, One Dockerfile, Deployed From the Infrastructure Repository

## Context

A frontend change rebuilt the backend, and the worker image carried the whole web app and every pipeline setting. The dataplatform on the same host uses one Dockerfile with a target per image, a uv workspace, git-tagged images for WUD, and deployment from `direkt-infrastructure`.

## Decision

- **Three Python packages** in one uv workspace with one `uv.lock`: `shared/` (database, gateway client, measuring code, queue, settings), `backend/` (API, live call, provisioning, scripts) and `worker/` (the wrap-up). `shared` imports neither of the others, and `backend` and `worker` never import each other; the job is queued by its dotted name. A test pins both rules. Each package's `pyproject.toml` lists what it imports.
- **One root `Dockerfile`** with targets `frontend`, `backend`, `worker`. Each Python image installs only its own package's closure. The frontend image is nginx serving the SPA, with `/config.js` (issuer, API URL, CSP) written at container start, so one image serves every environment.
- `scripts/build-and-push.sh` pushes each image as the pushed `v*` tag and `latest`, with provenance, so WUD can follow the digest. amd64 only.
- **Local development** runs the apps on the host against `dev-compose.yaml` (Postgres, Redis, Keycloak).
- **Deployment** is `direkt-infrastructure/public/calltrainer/compose.yml` on the DiReKT Hetzner host.

## Consequences

The worker image carries no FastAPI, KugelAudio or pypdf. A dependency declared in the wrong package fails in the image, not locally. A release is a pushed tag plus the build script; WUD rolls it out within the hour. The frontend's nginx rules are covered by no test.
