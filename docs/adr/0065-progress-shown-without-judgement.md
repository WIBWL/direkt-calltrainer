# ADR 0065: Progress Is Shown Without Being Judged

## Context

A progress chart asserts a direction just by how it is drawn: a rising line, a green band, an arrow. Nobody has established what "better" means for these figures in this population (ADR 0004/0051).

## Decision

The progress view shows the User's own values over time and does not evaluate them.

- **Permitted:** each metric's course, the descriptive history, and activity counts.
- **Not permitted:** target ranges or bands, arrows, deltas, words asserting improvement or decline, ranking against others, an aggregate score, or any colour that carries a value (ADR 0095). The traffic light of ADR 0078 stays on the single call.
- **Two halves side by side** (earlier and recent trainings, each as median ± spread) are allowed only on a metric's own page. Nothing is computed between them, columns are labelled by *when* and never *how*, the halves are equal and each above the series threshold, and both are drawn identically. The text says that Scenario and Persona differ between halves.

## Consequences

The view can be built from existing data without inventing a threshold. "Fortschritt" means development made visible, not measured improvement, and the interface must say so. If pilot data ever establishes real distributions, this ADR is replaced, not amended.
