# ADR 0038: Guard Against Degenerate Repetition; Guarantee a Closing Line on Backstopped Endings

## Status

Accepted

## Context

In testing, the small dialogue model would occasionally degenerate: repeating its own previous reply near-verbatim across Turns, or repeating a sentence within a single reply. Separately, a call can end via three different paths — the model's own `[CALL_END]` marker after being explicitly nudged (ADR 0037's closing check firing), the model including that marker completely unprompted, or (new here) a detected repetition — and only the nudged path actually asked the model to produce a goodbye line, so the other two paths could not be trusted to end with one.

## Decision

A reply that repeats the persona's immediately preceding message (case/whitespace-insensitive) or repeats one of its own sentences within itself is treated as an implicit signal that the call should end, on the reasoning that a model looping has nothing further to contribute. Whenever a call ends via the repetition path, or via an unprompted `[CALL_END]` that was never nudged, a fixed, pre-written German closing line is synthesized and appended instead of relying on whatever the model actually produced on those paths.

## Consequences

Every ended call now reliably closes with an audible, on-brand sign-off regardless of which path triggered the ending, and a degenerate repetition loop is cut short rather than continuing indefinitely or requiring the user to end the session manually. The trade-off is a small added latency and one extra synthesized utterance specifically on backstopped endings, and the repetition check itself is a heuristic (exact/near-exact match) that would not catch a differently-worded repetition of the same content.
