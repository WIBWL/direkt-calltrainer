# ADR 0018: Layered Modular Monolith for the Real-Time Path, Async Feedback Worker

## Context

The live call needs low latency. The wrap-up runs only after a call and can take its time.

## Decision

The real-time path is one deployable FastAPI service, layered into API, orchestration and data access, with no microservices. The wrap-up runs in a separate worker process fed by a job queue (ADR 0019).

## Consequences

The live path stays simple and fast. The wrap-up can be slow, retry and scale independently, at the cost of a queue and a second process.
