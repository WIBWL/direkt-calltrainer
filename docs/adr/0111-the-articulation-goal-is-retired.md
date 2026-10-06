# ADR 0111: "Deutliche Artikulation" Is Retired from the Focus Catalogue

## Context

A focus goal is a promise: it takes one of five slots and directs the app's attention. Articulation cannot be measured. The microphone cannot be factored out, Whisper tidies swallowed endings into correct words, and there would be no threshold. Counting the Persona's "Wie bitte?" would measure the recogniser. The other text-only goals live in what was said; articulation is exactly what the transcript does not carry.

## Decision

The `articulation` entry is removed from the seeded catalogue. The row is deactivated, not deleted, so past selections and tags still resolve. The served selection drops it, the wrap-up can no longer assign it, and positions stay contiguous. F-38 stays open in the feature list, answered with a reasoned no (ADR 0084).

## Consequences

A User who picked it keeps four goals and is not asked again. Old tags still count under the raw key until retention clears them. Re-adding the entry reactivates the row.
