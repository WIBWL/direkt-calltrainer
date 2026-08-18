# ADR 0019: Layered Modular Monolith for the Real-Time Path, Async Feedback Worker

## Status

Accepted

## Context

arc42's Bausteinsicht is still open. The backend today is a single file; the real Session pipeline needs a clear structure for orchestration (turns, retries per ADR 0017, Persona/Scenario), the EFRE-Direkt client (ADR 0011), and access to the project's own database (ADR 0010). Separately, Feedback generation (ADR 0004, ADR 0015) only ever runs after a Session ends and does not need to share the same request/response cycle as the live conversation.

## Decision

We will structure the real-time Session backend as a layered modular monolith — an API/interface layer, a dialog/orchestration logic layer, and a data-access layer (the EFRE-Direkt client and database access) — each independently swappable, within one deployable service (ADR 0012's FastAPI app). We will not split the real-time path into microservices. Feedback/wrap-up generation, however, runs as a separate asynchronous worker: ending a Session places a `SessionCompleted` event on a job queue, and the worker consumes it independently of the live conversation loop. Which model handles STT/LLM/TTS behind the EFRE-Direkt gateway (ADR 0011, ADR 0018) remains a configuration concern, not a service boundary.

## Consequences

The real-time path stays simple and low-latency where that matters most, while Feedback generation can take longer, retry independently, or scale separately without touching the conversation loop. This introduces a new infrastructure dependency (a job queue) and a second deployable process (the worker) — the concrete queue technology and its deployment are not yet decided.
