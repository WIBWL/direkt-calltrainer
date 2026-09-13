# ADR 0088: Intonation Is a Tile, and Its Page Carries the Drawing

## Status

Accepted. Removes `IntonationSection` from the wrap-up and the stored training; the metric's own page (`SessionMetricView`) is where the contour, the scale and the four factors are read. Reverses the earlier design in which intonation was "the one Kennzahl with a block instead of a tile". ADR 0077, written after this change, takes the tile's layout as given and moves the reading to the pitch variation quotient; ADR 0078 puts its traffic light on the reading. Neither changes what is recorded here.

## Context

F-35's reading appeared three times. As a **tile** in the metrics grid, with its figure and its reading. As a **block** under the grid (`IntonationSection`), with the figure again, the scale, the contour, the four factors and the note. And on the **metric's own page**, `/trainings/:id/kennzahl/intonation`, which rendered the same scale, the same note and the same contour and factors (`IntonationReading`). The block was a copy of the page placed inside the wrap-up. The tile's link to that page was even removed exactly when a contour existed, because the block below already showed it — so the place built for the drawing was hidden whenever there was a drawing.

The user found the topic long and asked for it to be compressed: into the half of the grid it belongs to (ADR 0082), with the detail one click away.

The tile itself had a second problem. It led with the range in semitones — "8,4 Halbtöne" — and put the reading under it. Semitones are the one unit in the inventory a reader cannot place, so the figure that led the tile said the least.

## Decision

**intonation is a tile like every other metric, and its page is where the drawing is.** `IntonationSection` and its styles are gone; the tile links to the page ("Diese Kennzahl ansehen"). Nothing on the page changed: the contour, the scale and the factors were already there.

**The tile leads with the reading, and the figure stays under it.** "lebendig", then "Einschätzung · 8,4 Halbtöne". Where there is too little voiced speech for a reading, the figure leads and the line under it says so: "Zu wenig Stimme für eine Einordnung".

It is the one tile that leads with a reading; every other tile leads with its measurement and lets the reading follow. The exception is for the reason above — the unit — and it is bounded: the measured figure is never dropped. Dropping it and keeping only the word was considered, since a figure nobody can place adds little, and rejected: that would keep the part resting on thresholds and discard the part that was measured, the wrong half to keep (ADR 0004, ADR 0051).

Since ADR 0077 the reading is taken from the pitch variation quotient while the tile's figure is the range. The figure is therefore no longer the evidence the reading rests on, only the measurement shown beside it; the argument for keeping it is unchanged.

## Consequences

The wrap-up has one section fewer, and intonation behaves like the other metrics: one tile, one page. The contour, which is the most informative part of F-35, is a click away rather than in view. That is the cost of the compression, and the reason the tile's link is always there now.

The tile's layout depends on the metric's key in `FeedbackView.tsx`, a special case beside the one for the opening's parts (ADR 0086). Two such cases are still readable; if more metrics come to need their own tile shape, a per-metric renderer would be the cleaner structure.
