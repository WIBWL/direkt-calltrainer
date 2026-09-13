# ADR 0082: The Metrics Are Shown in Two Halves, How and What

## Status

Accepted. Introduces `metric_type.aspect` (migration `b6d24f7a91e5`) and the slider above the metrics grid on the post-call screen and a stored training. A display decision: nothing in the analysis, the wrap-up prompt or the progress view reads the column. ADR 0051 stands untouched — every figure still describes the whole call (or, since ADR 0081, one of its two stretches) and none carries a target range.

## Context

The metrics grid started as six tiles (F-53) and grew. By the time this was decided it held talk share, questions, speaking pace, word count, reaction time, pauses, loudness and intonation, with more on the way (ADR 0083, ADR 0084, ADR 0086). A grid that long reads as a wall of numbers, and a wall of numbers invites the one reading this application works hardest to prevent: scanning for the good and the bad ones (ADR 0004).

The figures are not all the same kind of thing. Some describe the delivery — how fast, how loud, how much the pitch moved, how long before an answer. Others describe the exchange — how much room the user took, how many questions they asked, how many words they used. Communication training has long names for the two (paraverbal and verbal, or implicit and explicit feedback), and a user reading "Sprechtempo" next to "Fragen an den Gesprächspartner" is being asked to switch between two questions without being told they are two.

The Scenario library had already solved a similar problem with a slider over the grid (ADR 0072): one component, a radiogroup with a sliding thumb, each option showing how many cards it would yield.

## Decision

**Every metric belongs to one of two halves, and the screen shows one half at a time.** `how` is the delivery ("Wie Sie gesprochen haben"), `what` is the exchange ("Was Sie gesagt haben"). The same `FilterSlider` as the Scenario library sits above the grid, with the count of tiles on each side, and a line under it saying which question the half in view answers.

### The half is a column, not a frontend map

`metric_type.aspect`, CHECK-enforced to `how`/`what`, the same pattern as `scenario.category` (ADR 0072). The alternative was a key-to-half map in the frontend, which would have saved the migration and put a second source for the metric inventory beside `metrics.py`. The project's rule is that a metric is one `MetricDef` (ADR 0051) and `provision.py` seeds the reference table from it, so the half is a field on `MetricDef` and reaches the wire in `_measurement()` like the name and the unit beside it.

The column is nullable, and the migration backfills the rows that existed. Nullable because a key the inventory retires later would have no half to carry, and a `col IN (...)` CHECK passes for NULL. The frontend files anything without a half under `what`, so an unclassified metric still gets a tile rather than vanishing between the two.

### Where the borderline metrics go

**talk share is `what`**, although it is computed from durations. It describes the shape of the exchange — who held the floor — not the delivery of any sentence. reaction time is `how`: it is timing, and timing is delivery. intonation is `how`, and so is everything the audio alone measures.

**Wörter pro Satz is its own tile but not its own metric.** `_word_count` has always carried the average sentence length in its detail (F-08's second half). It is shown as a tile in the `what` half, built by the frontend from that detail, because a second `metric_type` row would store one number twice and let the copies drift.

### Details of the slider

It opens on `how`, the reading this trainer exists for and the one a user cannot take from the transcript. It hides itself when one half is empty — a switch onto nothing is a dead end — and then shows whatever there is. The disclaimer under the grid stays visible in both halves.

## Consequences

The grid is shorter on either side, and each half answers one question. The cost is that half the figures are one click away rather than in view; for a grid of eight to twelve tiles that is a trade worth making, where for three it would not have been.

Adding a metric is still one `MetricDef`, now with one more field. A test asserts that every metric in the inventory names a valid half and that both halves have active metrics, since the slider would otherwise never appear.

The progress view does not use the split. It groups metrics by focus goal (ADR 0076, ADR 0080), and a second grouping there would compete with the first.
