# ADR 0038: Guard Against Degenerate Repetition; Guarantee a Closing Line on Backstopped Endings

## Status

Accepted

## Context

In testing, the small dialogue model would occasionally degenerate: repeating its own previous reply near-verbatim across Turns, or repeating a sentence within a single reply. Separately, a call can end via three different paths — the model's own `[CALL_END]` marker after being explicitly nudged (ADR 0037's closing check firing), the model including that marker completely unprompted, or (new here) a detected repetition — and only the nudged path actually asked the model to produce a goodbye line, so the other two paths could not be trusted to end with one.

## Decision

A reply that shows any of the following is treated as an implicit signal that the call should end, on the reasoning that a model looping has nothing further to contribute:

- **repeats one of its own sentences** within itself;
- **is verbatim the immediately preceding reply** (case/whitespace-insensitive), at any length — an exact back-to-back repeat is degenerate however short it is;
- **is verbatim a reply from further back than the previous Turn** — the model tends to oscillate (A-B-A-B), where the repeat is two Turns back and a "same as last reply" check walks straight past it; this one carries a short-acknowledgement length floor, since a brief line ("Ja, genau.") can legitimately recur across a longer call;
- **restates most of the previous reply** — more than half of its comparable sentences were already there. The verbatim checks never fire in practice because the persona varies its opening sentence and carries the same block underneath it Turn after Turn, so what separates a loop from a caller legitimately quoting a figure twice is *how much* of the reply is old, not *whether* a sentence came back.

Whenever a call ends via the repetition path, or via an unprompted `[CALL_END]` that was never nudged, a fixed, pre-written German closing line is synthesized and appended instead of relying on whatever the model actually produced on those paths.

## Consequences

Every ended call now reliably closes with an audible, on-brand sign-off regardless of which path triggered the ending, and a degenerate repetition loop — verbatim, oscillating, or a fresh-worded restatement of the same content — is cut short rather than continuing indefinitely or requiring the user to end the session manually. The trade-off is a small added latency and one extra synthesized utterance specifically on backstopped endings, and the checks remain heuristics: the share threshold is tuned against a handful of real calls (a restatement measured ~80%, a reply that moved the call on ~25%), so a reply that reworks the same content into all-new sentences, or restates a reply from several Turns back rather than the immediately previous one, can still slip through.
