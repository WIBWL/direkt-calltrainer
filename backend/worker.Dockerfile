# The Feedback worker (ADR 0018/0019): the backend's code and dependencies, a
# different process and no port. Built from the repository root (compose.yaml).
# RQ forks per job, so this only ever runs on Linux.

# Pinned to 3.12 for the same reason as backend/Dockerfile; raise both together.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

WORKDIR /app
COPY alembic.ini ./
COPY backend/ backend/
COPY scripts/ scripts/

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

CMD ["python", "-m", "backend.worker"]
