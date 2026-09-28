# syntax=docker/dockerfile:1.7
# Three images from one Dockerfile: frontend, backend, worker (ADR 0104).
#   docker build --target <name> -t <tag> .
# scripts/build-and-push.sh builds and pushes all three. amd64 only:
# praat-parselmouth ships no Linux aarch64 wheel.


# --- Python ------------------------------------------------------------------

# Pinned, not "python:3-slim": that floating tag had already moved to 3.14, where
# SQLAlchemy 2.0.36 cannot resolve the `Mapped[int | None]` annotations in
# shared/db/models.py and every database import dies. Raise it together with
# .python-version and requires-python.
FROM python:3.12-slim AS python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app


# Each image's dependencies, and nothing else: `--package` installs one
# workspace member's closure from the one lockfile. Only the pyproject files are
# copied, so this layer caches across source edits.
FROM python AS python-deps
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
COPY shared/pyproject.toml  ./shared/
COPY backend/pyproject.toml ./backend/
COPY worker/pyproject.toml  ./worker/

FROM python-deps AS backend-deps
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --locked --no-dev --package calltrainer-backend

FROM python-deps AS worker-deps
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --locked --no-dev --package calltrainer-worker


# What both Python images run as. The packages are imported from /app, not
# installed (they are virtual workspace members), hence PYTHONPATH. JSON logs
# for the host's log shipper (ADR 0105).
FROM python AS python-runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    LOG_FORMAT=json
RUN adduser --uid 5678 --disabled-password --gecos "" appuser


# Env: every setting in .env.example (ADR 0106), any as NAME_FILE; CORS_ORIGINS
# optional. No ENTRYPOINT: migrations and seeding run in the app's lifespan
# handler (backend/db/provision.py). The scripts come along for
# `docker compose exec ... python -m backend.scripts.<name>`.
FROM python-runtime AS backend
COPY --from=backend-deps /opt/venv /opt/venv
COPY shared  ./shared
COPY backend ./backend
USER appuser
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "120", "backend.app:app"]


# Env: DIREKT_URL, DIREKT_API_KEY, LLM_MODEL, POSTGRES_URL, REDIS_URL, and
# POSTGRES_PASSWORD if the URL carries none -- any as NAME_FILE. No port.
# RQ forks per job (ADR 0018/0019).
FROM python-runtime AS worker
COPY --from=worker-deps /opt/venv /opt/venv
COPY shared ./shared
COPY worker ./worker
USER appuser
CMD ["python", "-m", "worker"]


# --- Frontend ----------------------------------------------------------------

# Dependencies first so this layer caches across source edits. `npm run build`
# lints, type-checks (specs included) and copies the VAD runtime into public/.
FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,id=npm,target=/root/.npm \
    npm ci
COPY frontend/ ./
RUN npm run build


# Env (read by render-config.sh at start):
#   OIDC_ISSUER   required, the realm the backend checks tokens against
#   API_URL       the backend's origin; unset means the SPA's own
FROM nginx:1-alpine AS frontend
COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY frontend/docker/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/docker/render-config.sh /docker-entrypoint.d/10-render-config.sh
RUN chmod +x /docker-entrypoint.d/10-render-config.sh
EXPOSE 80
