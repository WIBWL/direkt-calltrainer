# ADR 0038: Guard Against Degenerate Repetition; Guarantee a Closing Line on Backstopped Endings

## Context

Small models loop: they repeat their last reply, oscillate A-B-A-B, re-introduce themselves, or carry the same block under a new opening line.

## Decision

Repetition is handled cheapest first:

1. **Prompt:** the call is already open, so no greeting, no name, no restating the reason.
2. **Per-turn nudge:** a transient system message quotes the Persona's last reply and asks for something new. A `hard` Persona gets a stronger version.
3. **Before synthesis:** a first chunk that re-greets or opens with an already-said sentence is regenerated once. Sentences already said verbatim are dropped from any chunk, so only new content is spoken.
4. **Backstop after speaking:** a reply that repeats its own sentence, equals an earlier reply verbatim, or restates more than half of the previous one ends the call.

A user's request to repeat swaps in a "reword it shorter" nudge and relaxes the checks against the previous reply, for the first such request only.

A call ended by the backstop or by an unprompted `[CALL_END]` gets a fixed, pre-written closing line.

## Consequences

Loops are cut short, and every ending is audible. The thresholds are heuristics tuned on a handful of calls, and a full rewording of old content still slips through.
