# ADR 0016: Persona Selection via Card View, Not a List

## Status

Accepted

## Context

Before starting a Session, the user picks a Persona from the library (ADR 0002). This could be presented as a plain list or dropdown of names, or as cards that preview each Persona's role, difficulty, and character traits before selecting.

## Decision

We will present Persona selection as cards, each showing a short profile (role, difficulty, characteristic traits), not a plain list or dropdown of names.

## Consequences

Users can judge fit and difficulty before starting a Session, without opening each Persona individually — supporting the low-friction setup goal (ADR 0014). As the Persona library (ADR 0002) grows, the card grid needs its own layout and scaling treatment (search/filter), which a plain list would not have required.
