# ADR 0023: Language as Independent Session Parameter

## Status

Accepted (supersedes ADR 0006)

## Context

The Persona's system prompt originally hard-coded the simulated conversation's language to German. The product now wants the user to choose the language a Session runs in from a setting on the training page, independent of which Persona or Scenario they picked — the same Persona should be usable in German or English without change. This supersedes ADR 0006 (German only for the MVP) and the arc42 Randbedingung F-18, which stated the training must run in German only, with English "explicitly not a goal."

## Decision

We will model Language as a third independent, user-configurable Session parameter, alongside Scenario (ADR 0001) and Persona — not as a property baked into a specific Persona definition.

## Consequences

Any Persona can run in any supported language without duplicating Persona definitions per language. The trade-off: Persona content such as example objections is currently authored in one language (German) and must be adapted to the target language by the LLM at request time, rather than sourced from curated, language-specific text — translation fidelity depends on the model, not on curated content, until/unless Personas grow per-language content. F-18 in arc42 no longer reflects reality and has been updated to describe language as a configurable setting instead of a fixed German-only requirement.
