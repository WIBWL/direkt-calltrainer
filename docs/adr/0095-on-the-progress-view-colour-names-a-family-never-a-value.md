# ADR 0095: On the Progress View, Colour Names a Family and Never a Value

## Context

ADR 0065 says what colour may not do on the progress view. Without a positive rule, defaults creep back: a hue per metric, green for "in range", red/amber/green as decoration.

## Decision

- **One hue per family:** Sprechweise `--series-speech` `#2a78d6`, Gesprächsinhalt `--series-content` `#e87ba4`, Aktivität `--series-activity` `#4a3aa7`. They were validated as a set for colour-vision deficiency. A metric's family comes from `metric_type.aspect`.
- `colorOf(aspect)` never receives a value, so no number can move a colour.
- Red, amber and green are never used for identity; they belong to ADR 0078.
- Magnitude is shaded on one hue only, and only as a second reading of a number printed beside it.
- Groupings that are not metric families get no colour.

## Consequences

Colour cannot single out a metric here; position and type do. A fourth family means re-validating the set.
