# ADR 0095: On the Progress View, Colour Names a Family and Never a Value

## Status

Accepted. Complements ADR 0065, which says what colour may not do on the progress view, with the rule for what it does there. Leaves ADR 0078's traffic light on the single call untouched.

## Context

ADR 0065 rules out colour that means good or bad across trainings: no target bands, no green for an improvement. It does not say what colour is for. A dashboard with sixteen Kennzahlen, a calendar and a variety table still needs colour to be legible — at the least to show which charts belong together.

Without a positive rule the easy defaults come back one chart at a time: a hue per metric, which is sixteen hues and indistinguishable neighbours under a colour vision deficiency; green for a value inside the usual range, which is exactly the judgement ADR 0065 excludes; red, amber and green used as decoration, although ADR 0078 has given those three a meaning on the single-call view.

## Decision

**One hue per family, and three families:** Sprechweise, Gesprächsinhalt and Aktivität. A metric's family comes from `metric_type.aspect` on the wire (ADR 0082), not from a map in the frontend, so a metric added in the backend needs no colour decision.

| family | custom property | value |
|---|---|---|
| Sprechweise | `--series-speech` | `#2a78d6` |
| Gesprächsinhalt | `--series-content` | `#e87ba4` |
| Aktivität | `--series-activity` | `#4a3aa7` |

They are slots 1, 5 and 7 of the categorical palette, validated as an all-pairs set against a white card: ΔE 13.0 under simulated colour vision deficiency against a target of 8, ΔE 16.3 in normal vision against a floor of 15. The magenta sits at 2.69:1 against the card, below 3:1; that is admissible only because every mark is also printed as a figure and the metric's own page repeats the values as a table.

**Two structural rules keep it identity:**

1. **The function that assigns a colour never receives a value.** `colorOf(aspect)` takes the family and nothing else, so no number can move a colour — which is precisely what a traffic light does.
2. **Red, amber and green are not used for identity.** They belong to ADR 0078 on the single call, and a hue that means something there must not carry something else here.

**Magnitude is shaded on one hue only, and only as a second reading of a number printed beside it.** The calendar shades a day in three steps of the activity hue (mixed with the surface at 45 % and 70 %, validated as an ordinal ramp: monotone lightness, adjacent gaps over 0.06, light end 2.23:1) and prints the count in the cell. The variety table's cell fill repeats the count written in it. Where a shade would read as "more is better", nothing is shaded: every mark on the checklist strip (`PartsStrip`) looks alike whatever it holds.

**Groupings that are not metric families get no colour.** The focus-goal groups are numbered (`FocusGoalPicker`), and whether a quoted wrap-up sentence was a strength or an improvement is written out in words (`GoalStatements`).

## Consequences

Colour cannot be used to single out one metric of interest on this screen. Emphasis comes from position and type instead: the focus goals lead the page, and the table orders its rows by family.

A fourth family would mean validating the set again; a fourth hue picked by eye is the failure this ADR exists to prevent.

The hues live as custom properties in `index.css` and are referenced by name from TypeScript, so the palette has one home. The single-call view keeps its own rules (ADR 0078), and the two views must not be merged into one palette.
