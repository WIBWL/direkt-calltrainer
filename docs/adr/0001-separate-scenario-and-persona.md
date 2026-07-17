---
status: proposed
---

# Separate Scenario and Persona concepts

## Context

A Session needs to be configured with both a situational context (why the call is happening) and a character for the AI counterpart (how they behave).

## Decision

Model these as two independent, separately configurable concepts — Scenario and Persona — rather than a single combined configuration field.

## Consequences

Either can be varied independently of the other (e.g. the same Scenario paired with a calm or an impatient Persona), at the cost of an extra configuration axis when setting up a Session.
