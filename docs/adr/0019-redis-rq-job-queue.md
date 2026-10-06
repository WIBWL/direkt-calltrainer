# ADR 0019: Redis + RQ for the Feedback Job Queue

## Context

The wrap-up worker (ADR 0018) needs a queue. The candidates were Celery, FastAPI's `BackgroundTasks`, and Redis with RQ.

## Decision

Redis with RQ. The backend enqueues one job per stored Session, and the worker process consumes it. The job is referenced by name, so the backend never imports the worker.

## Consequences

The queue is durable and survives restarts, unlike `BackgroundTasks`, and is lighter than Celery for a single job type. Redis is one more service to run.
