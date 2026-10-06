# ADR 0011: Speech Recognition and Dialogue Run on the DiReKT Gateway

## Context

The university provides an OpenAI-compatible gateway, at no cost and without third-party commercial APIs. Using it is a project requirement.

## Decision

Speech recognition and all text generation (the live reply and everything written after the call) run on the DiReKT gateway (ADR 0103). Speech output is KugelAudio. Session data is stored in the project's own database (ADR 0010).

## Consequences

There are no commercial LLM costs and data residency is clear. Availability, model choice and rate limits are outside the project's control.
