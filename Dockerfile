# For more information, please refer to https://aka.ms/vscode-docker-python

FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# OIDC config is baked into the SPA at build time (see frontend/src/oidcConfig.ts).
# compose.yaml passes these; a bare `docker build` falls back to the local defaults.
ARG VITE_OIDC_ISSUER=http://localhost:18081/realms/direkt
ARG VITE_OIDC_CLIENT_ID=calltrainer-frontend
ENV VITE_OIDC_ISSUER=$VITE_OIDC_ISSUER
ENV VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID
RUN npm run build

# Pinned, not "python:3-slim": that floating tag silently follows new Python
# major releases. It had already moved to 3.14, where SQLAlchemy 2.0.36 cannot
# resolve the `Mapped[int | None]` annotations in backend/db/models.py and every
# database import dies. 3.12 is what the project is developed and tested against;
# raise it deliberately, together with the pins in requirements.txt.
FROM python:3.12-slim

EXPOSE 8000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

WORKDIR /app
COPY . /app
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN chmod +x /app/docker-entrypoint.sh

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Migrations and reference-data seeding run before the CMD below; see the script.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "120", "backend.app:app"]
