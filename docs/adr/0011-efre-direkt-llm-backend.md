# ADR 0011: LLM Backend Is the University-Hosted EFRE-Direkt Gateway, Self-Contained

## Status

Accepted

## Context

The project needs STT, dialogue-generation, and TTS capabilities. The university provides a hosted, OpenAI-compatible gateway (`efre-direkt.de`), backed by a vLLM engine, at no cost to the project and without sending data to third-party commercial APIs. Using this gateway is a project requirement, not merely a convenient default — it is not being picked from among competing commercial providers.

## Decision

We will use the university-hosted efre-direkt gateway as the sole backend for STT, Persona dialogue generation, and TTS. No audio or text data leaves this gateway during LLM processing; the only external data flow in the system is uploaded documents and Session metadata going to the Datenplattform (see ADR 0010).

## Consequences

No commercial LLM API costs, and a clear, university-hosted data-residency story for the LLM-processing leg of the pipeline. In exchange, the project depends on the university's infrastructure — availability, model choice, and rate limits are outside the project's control — and this single gateway is a single point of failure for all three AI capabilities.
