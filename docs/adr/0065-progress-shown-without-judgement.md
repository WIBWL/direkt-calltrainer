# ADR 0065: Progress Is Shown Without Being Judged

## Status

Accepted. Extends ADR 0004 and ADR 0051 to the multi-Session view; constrains ADR 0064's data.

## Context

ADR 0064 makes a user's Sessions readable as a series, which is what F-13 (Aufzeichnung des Fortschritts) asks for. The obvious next step is a view that plots the Kennzahlen over time — and the obvious way to draw that view is the one this project has twice decided against.

ADR 0004 rejected reducing performance to a score, on the pilot stakeholder's explicit request. ADR 0051 went further for the per-Session statistics: no metric carries a target range, because none is validated for this population, and "an invented threshold is a score in disguise". The wrap-up prompt enforces it in writing (`generator.py`: no score, grade, rating, percentage or star, and no judging a figure against a norm).

A progress view puts that under quiet pressure in a way a single Session never did. A line going up asserts a direction whether or not anyone chose to assert one. A green band asserts a target. Even an arrow and the word "besser" asserts that more questions, or a higher Redeanteil, or a faster Sprechtempo, is an improvement — and nobody has established that for this population. The risk is not that someone argues for a score; it is that the score arrives as a styling decision, made by whoever draws the chart, without the discussion ADR 0004 had.

## Decision

The progress view shows the user their own values over time and does not evaluate them.

Permitted, and the substance of F-13: the course of each Kennzahl across Sessions, plotted plainly; the descriptive history of F-48 (when, which Scenario, which Persona, how long, completed or aborted); and activity figures such as how many trainings were done in a period. Activity needs no norm — it counts what the user did, not how well.

Not permitted without a further, explicit decision: target ranges or bands; arrows, deltas or labels asserting improvement or decline; ranking against other users; and any aggregate score over Sessions. `metric_type` has no target column and gains none — the absence is the mechanism, not an oversight, exactly as in ADR 0051.

Consistent with this, ADR 0064's endpoint returns raw measured values and no interpretation, and `feedback.score` stays unwritten. ADR 0004 does permit a numeric score as a supplementary addition that never replaces the qualitative feedback, so the column remains; this ADR declines to introduce one *across* Sessions, where it would be a ranking of a person over time rather than a note about one call.

The peak-end weighting stays what ADR 0004 made it: text weight in the wrap-up, never a number, and it does not extend across Sessions.

## Consequences

The progress view can be built now, from data that already exists, without inventing a single threshold — which is why this is a constraint rather than a blocker. What the user gets is honest: their own behaviour made visible over time, with the interpretation left to them and to the qualitative feedback that ADR 0003 and ADR 0004 made the product's actual output.

The cost is that the view is less immediately gratifying than a dashboard with a big green number, and "Fortschritt" in the UI has to mean *development made visible* rather than *measured improvement*. That gap should be named in the interface rather than papered over, or users will supply the missing judgement themselves and assume up is good.

This decision is falsifiable and expected to be revisited: if the pilot produces enough Sessions to establish what a distribution of these values actually looks like for this population, then a norm would rest on measurement rather than on invention, and a target range would become a defensible thing to draw. Until that data exists, an evaluative progress view would be asserting knowledge nobody has. Whoever revisits this should replace this ADR rather than amend a chart.
