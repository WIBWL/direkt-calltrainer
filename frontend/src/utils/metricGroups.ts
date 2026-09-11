import type { MetricAspect } from "../protocol";

/**
 * Which family a Kennzahl belongs to, and the colour that says so (F-13).
 *
 * **Colour here is identity, never judgement.** ADR 0065 rules out any colour on
 * this screen that means good or bad; it does not rule out colour that means
 * "these belong together". The whole of the distinction is two rules, and both
 * are structural rather than a matter of care:
 *
 * 1. **The hue hangs off the metric, not off its value.** Nothing in this module
 *    takes a number. A value can therefore never change a colour, which is what
 *    a traffic light does.
 * 2. **Red, amber and green do not appear.** Not because they would be ugly, but
 *    because this application already spent them: ADR 0078's traffic light uses
 *    exactly those three on the single-call view, so reusing one here as an
 *    identity hue would collide with a reserved meaning and invite the reading
 *    the rule above forbids.
 *
 * The three hues are slots 1, 5 and 7 of the documented categorical palette,
 * kept in that order. Validated as an all-pairs set against a white card
 * surface: CVD ΔE 13.0 (protan) against a target of 8, normal-vision ΔE 16.3
 * against a floor of 15. Magenta falls below the 3:1 contrast line at 2.69,
 * which the palette rules permit where the value is readable another way — here
 * every tile prints its figure as text and the detail level repeats the series
 * as a table, so the colour is never the only carrier.
 *
 * Three and not ten. A hue per Kennzahl would put eight colours on one screen,
 * where adjacent pairs stop being distinguishable under a colour vision
 * deficiency, and the hue would then encode nothing but variety.
 */

export type MetricGroup = "speech" | "content" | "activity";

export interface GroupStyle {
  /** The German heading this family appears under. */
  label: string;
  /** The hue, as a CSS custom property defined in index.css. Referenced rather
   *  than repeated, so the palette has one home. */
  color: string;
}

export const GROUPS: Record<MetricGroup, GroupStyle> = {
  // Slot 1, blue. The family with the most members and the one nearest the
  // application's own navy, so the screen still reads as this product.
  speech: { label: "Sprechweise", color: "var(--series-speech)" },
  // Slot 5, magenta.
  content: { label: "Gesprächsinhalt", color: "var(--series-content)" },
  // Slot 7, violet. Counting what somebody did needs no norm at all, which is
  // why the two charts in this family are the only ones on the screen that
  // carry no caveat.
  activity: { label: "Aktivität", color: "var(--series-activity)" },
};

/**
 * The family of one Kennzahl, from the `aspect` the schema already stores.
 *
 * Read off the wire rather than mapped here: `metric_type.aspect` is assigned in
 * `backend/feedback/metrics.py` and travels with every measurement, so a metric
 * added there needs no edit in the frontend. A measurement with no aspect falls
 * to `speech`, matching the backend's own fallback for an unclassified metric.
 */
export function groupOf(aspect: MetricAspect | null | undefined): MetricGroup {
  return aspect === "what" ? "content" : "speech";
}

/** The hue of one Kennzahl, for a chart mark. */
export function colorOf(aspect: MetricAspect | null | undefined): string {
  return GROUPS[groupOf(aspect)].color;
}
