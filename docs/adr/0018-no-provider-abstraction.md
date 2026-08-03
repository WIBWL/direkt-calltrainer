# ADR 0018: No Provider Abstraction Layer for STT/LLM/TTS

## Status

Accepted

## Context

arc42 flags component swappability (e.g. exchangeable LLM/STT/TTS components) as an open maintainability target (Kapitel 8). However, the EFRE-Direkt gateway is a fixed project requirement (ADR 0011), not a choice among competing providers — there is no second provider in view to swap to.

## Decision

We will call the EFRE-Direkt OpenAI-compatible API directly wherever STT, dialogue generation, or TTS is needed, without introducing a provider-abstraction interface. Each capability is called from one clearly separated place in the code.

## Consequences

Avoids speculative complexity for a swap that has no concrete second provider to design against today. If a second provider ever becomes necessary, introducing an abstraction then is a contained change, since each capability already has a single, well-defined call site.
