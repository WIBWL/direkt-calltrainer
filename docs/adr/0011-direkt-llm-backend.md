# ADR 0011: LLM Backend Is the University-Hosted DiReKT Gateway, Self-Contained

## Status

Accepted (scope narrowed to dialogue generation by ADR 0021 — see below)

## Context

The project needs STT, dialogue-generation, and TTS capabilities. The university provides a hosted, OpenAI-compatible gateway (the DiReKT gateway), backed by a vLLM engine, at no cost to the project and without sending data to third-party commercial APIs. Using this gateway is a project requirement, not merely a convenient default — it is not being picked from among competing commercial providers.

In practice, DiReKT turned out to provide API access for the dialogue/reasoning model only. STT and TTS are not available through it and had to move to separately self-hosted models — see ADR 0021, which narrows this ADR's scope.

## Decision

We will use the university-hosted DiReKT gateway as the backend for Persona dialogue generation. No text data leaves this gateway during that processing; the only external data flow in the system is uploaded documents travelling through the Data Platform, plus audio going to the separately self-hosted STT/TTS models (ADR 0021). Session data itself is stored in the project's own database (ADR 0010).

## Consequences

No commercial LLM API costs, and a clear, university-hosted data-residency story for the dialogue-generation leg of the pipeline. In exchange, the project depends on the university's infrastructure for this leg — availability, model choice, and rate limits are outside the project's control.
