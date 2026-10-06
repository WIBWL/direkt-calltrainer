# ADR 0017: No Provider Abstraction Layer for STT/LLM/TTS

## Context

The gateway is a project requirement (ADR 0011), and there is no second provider in view.

## Decision

Each capability calls its API directly from one place in the code. There is no provider interface, registry or runtime switch.

## Consequences

No speculative complexity. Adding a second provider later is a contained change, because each capability has a single call site.
