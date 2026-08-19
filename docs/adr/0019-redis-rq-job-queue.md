# ADR 0019: Redis + RQ for the Feedback Job Queue

## Status

Accepted

## Context

ADR 0018 decouples Feedback/wrap-up generation from the real-time Session loop via a `SessionCompleted` event on a job queue, consumed by a separate async worker. A concrete queue technology was still open. Candidates considered: Celery with RabbitMQ/Redis, FastAPI's built-in `BackgroundTasks`, or Redis with RQ.

## Decision

We will use Redis with RQ (Redis Queue) as the job queue between the real-time Session service and the Feedback worker. The real-time service enqueues a `SessionCompleted` job when a Session ends; the worker, a separate process, dequeues and processes it.

## Consequences

Gives a real, separately running worker process with a durable queue (survives a container restart, unlike in-process `BackgroundTasks`), at the cost of one more service to run (Redis) and deploy (a `compose.yaml` entry plus the worker process itself). This is deliberately lighter than Celery, since the current use case is a single job type (post-Session feedback generation), not a system needing scheduling, complex routing, or multiple queues.
