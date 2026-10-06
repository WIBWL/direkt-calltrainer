# ADR 0056: Phase-Appropriate Language Is a Paragraph, Not a Metric

## Context

F-42 asks whether the register fits each phase of the call: a warm opening, a factual core, a warm closing. What matters is the *movement* between phases. A figure for that would need a reference corpus or an invented norm.

## Decision

F-42 ships as prose: `feedback.phase_language`, written in the same model call as the rest of the wrap-up and shown as its own block. The closing gets more weight in the text (peak-end rule) and has first claim on the block's one suggestion. The field is nullable, and empty means the block is omitted. The `phase_appropriate_language` metric stays seeded and inactive.

## Consequences

F-42 is covered without a threshold. It is the one part of the wrap-up with no deterministic backing: phase boundaries are the model's judgement and cannot be checked.
