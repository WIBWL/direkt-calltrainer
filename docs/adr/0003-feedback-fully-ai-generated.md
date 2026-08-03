# ADR 0003: No Human Trainer — Feedback Is Fully AI-Generated

## Status

Accepted

## Context

Traditional communication training often pairs a trainee with a human coach who observes the call and gives feedback. This product's domain model has no such role: the User performs a Session alone, against an AI-simulated counterpart.

## Decision

We will generate all Feedback for a Session entirely through the AI system. No human coach or trainer is part of the product's runtime loop.

## Consequences

The product stays self-service and scalable without needing human coaching capacity. In exchange, Feedback quality depends entirely on the AI's ability to assess communication behavior faithfully — there is no human fallback to correct a misjudgment, and users may distrust feedback that feels wrong (see arc42, Risiken: Subjektivität von Feedback).
