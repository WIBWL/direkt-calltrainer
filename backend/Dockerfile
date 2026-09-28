# The API and the live session. Built from the repository root (compose.yaml),
# since it needs alembic.ini, requirements.txt and scripts/ beside backend/.
# The SPA is its own image (frontend/Dockerfile) and never lands in this one.

# Pinned, not "python:3-slim": that floating tag silently follows new Python
# major releases. It had already moved to 3.14, where SQLAlchemy 2.0.36 cannot
# resolve the `Mapped[int | None]` annotations in backend/db/models.py and every
# database import dies. 3.12 is what the project is developed and tested against;
# raise it deliberately, together with the pins in requirements.txt.
FROM python:3.12-slim

EXPOSE 8000

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

WORKDIR /app
COPY alembic.ini ./
COPY backend/ backend/
# The requeue, retention and check scripts are run inside the container, where
# Redis is reachable (`docker compose exec backend python scripts/...`).
COPY scripts/ scripts/

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# No ENTRYPOINT: migrations and seeding run in the app's lifespan handler
# (backend/db/provision.py).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "120", "backend.app:app"]
