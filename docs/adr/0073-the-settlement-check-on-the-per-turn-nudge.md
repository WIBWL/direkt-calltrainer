# ADR 0073: The Settlement Check Rides on the Per-Turn Nudge

## Context

Across 34 scripted pairings, the Persona never closed when its success condition was met. It closed only after the user's goodbye, because the nudge nearest the reply offered six ways to continue and none to stop.

## Decision

- From the Persona's third reply on, the per-turn nudge carries a settlement check that restates the success condition, or a generic criterion if there is none.
- It is phrased as a question with the open case first, and does not name the marker. Phrased as an order, it made the model hang up on its opening question.
- The system prompt's prohibition was halved, keeping every constraint.

Measured: correct closings went 0 → 6 of 34, premature endings 0 → 1.

## Consequences

The prompt moves the result from "never" to "sometimes"; the rest is the model's limit. A reliable trigger would be a separate model call judging the condition off the reply path, which is not built.
