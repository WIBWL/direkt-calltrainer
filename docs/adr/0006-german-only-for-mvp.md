# ADR 0006: Training Language Is German Only for the MVP

## Status

Superseded by ADR 0022 (Language as Independent Session Parameter)

## Context

The pilot customer and its support/project staff operate in German. Supporting multiple languages upfront would add translation and Persona-voice complexity before the core Session loop is validated.

## Decision

We will run all Session dialogue and Feedback in German for the MVP. English is explicitly out of scope for now.

## Consequences

This reduces the STT/LLM/TTS configuration and prompt-engineering surface to a single language, speeding up MVP delivery. Extending to other languages later requires revisiting prompts, voice/TTS model selection, and possibly this decision itself.
