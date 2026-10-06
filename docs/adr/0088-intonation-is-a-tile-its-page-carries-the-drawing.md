# ADR 0088: Intonation Is a Tile, and Its Page Carries the Drawing

## Context

F-35's reading appeared three times: as a tile, as a block under the grid, and on its own page.

## Decision

Intonation is a tile like the others, linking to its page, which holds the contour, the scale and the factors. The tile leads with the reading ("lebendig") and keeps the semitone figure beneath it, because semitones are a unit nobody can place. With too little voiced speech, the figure leads and says so.

## Consequences

The wrap-up is shorter and the contour is a click away. Tile layout special-cases two metric keys (intonation, the checklist metrics); more would call for a per-metric renderer.
