# syntax=docker/dockerfile:1.7
# Three images, one per target: frontend, backend, worker (ADR 0108). amd64 only:
# praat-parselmouth ships no Linux aarch64 wheel.

# Pinned with .python-version: on 3.14 SQLAlchemy 2.0.36 cannot resolve the models.
FROM python:3.12-slim AS python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app


# One workspace member's closure each; only the pyproject files, so the layer caches.
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


# The packages are imported from /app, not installed, hence PYTHONPATH.
FROM python AS python-runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    LOG_FORMAT=json
RUN adduser --uid 5678 --disabled-password --gecos "" appuser


# One gunicorn worker: the per-account caps are counted in it (ADR 0109).
FROM python-runtime AS backend
COPY --from=backend-deps /opt/venv /opt/venv
COPY shared  ./shared
COPY backend ./backend
USER appuser
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "-k", "backend.gunicorn_worker.Worker", "--timeout", "120", "backend.app:app"]


FROM python-runtime AS worker
COPY --from=worker-deps /opt/venv /opt/venv
COPY shared ./shared
COPY worker ./worker
USER appuser
CMD ["python", "-m", "worker"]


FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,id=npm,target=/root/.npm \
    npm ci
COPY frontend/ ./
# `npm run build` runs eslint and tsc but not vitest.
RUN npm test
RUN npm run build


# render-config.sh reads OIDC_ISSUER (required) and API_URL at start.
FROM nginx:1-alpine AS frontend
COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY frontend/docker/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/docker/render-config.sh /docker-entrypoint.d/10-render-config.sh
RUN chmod +x /docker-entrypoint.d/10-render-config.sh
EXPOSE 80
