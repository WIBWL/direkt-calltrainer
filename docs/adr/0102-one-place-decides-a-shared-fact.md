# ADR 0102: One Place Decides a Shared Fact

## Context

A review found facts worked out independently in several places that had drifted: the PDF omitted what the page showed, the progress overview linked to an empty detail page, and the stored-call fold ignored `reverse`.

## Decision

A fact that more than one reader needs is decided in one module, and the readers ask it:

1. `utils/reportOutline.ts`: what the feedback report says, rendered by both the page and the PDF.
2. `utils/progressOutline.ts`: what each focus goal reads on the progress view and in its PDF.
3. `shared/feedback/stored.py`: how a stored Session is read back, including language and casting.
4. `deletion.remove`: the order in which a Session and what hangs off it are removed, used by all three deletion paths.
5. `progressStats.selectionSeries` and `completedOnly`: the series a selection has, and which trainings count.
6. `reply_checks.ending`: whether a reply ends the call and whether a goodbye must follow.

The same rule covers smaller cases: `SpokenReply.cut`, `nudges.for_turn`, `owned_session`, `useTrainingRun`.

## Consequences

Each owner is pure or takes its session from the caller, and is tested through its own interface. Before working a fact out where it is needed, look for the module that already answers it.
