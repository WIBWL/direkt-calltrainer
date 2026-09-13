import type { MetricAspect } from "../protocol";

/**
 * Which family a metric belongs to, and the colour that says so (F-13).
 *
 * **Colour here is identity, never judgement.** ADR 0065 rules out colour that
 * means good or bad, not colour that means "these belong together". Two
 * structural rules hold the line:
 *
 * 1. **The hue hangs off the metric, not its value.** Nothing here takes a
 *    number, so a value can never move a colour — which is what a traffic light
 *    does.
 * 2. **Red, amber and green do not appear.** ADR 0078's traffic light already
 *    spent those three on the single-call view; reusing one as an identity hue
 *    would collide with a reserved meaning.
 *
 * Slots 1, 5 and 7 of the documented categorical palette, validated as an
 * all-pairs set against a white card: CVD ΔE 13.0 against a target of 8,
 * normal-vision ΔE 16.3 against a floor of 15. Magenta sits at 2.69 against the
 * 3:1 line, which the palette permits where the value is readable another way —
 * every tile prints its figure and the detail level repeats it as a table.
 *
 * Three and not ten: a hue per metric would be eight colours on one screen,
 * where adjacent pairs stop being separable under a colour vision deficiency.
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
 * The family of one metric, from the `aspect` the schema already stores.
 *
 * Read off the wire rather than mapped here: `metric_type.aspect` is assigned in
 * `backend/feedback/metrics.py` and travels with every measurement, so a metric
 * added there needs no edit in the frontend. A measurement with no aspect falls
 * to `speech`, matching the backend's own fallback for an unclassified metric.
 */
export function groupOf(aspect: MetricAspect | null | undefined): MetricGroup {
  return aspect === "what" ? "content" : "speech";
}

/** The hue of one metric, for a chart mark. */
export function colorOf(aspect: MetricAspect | null | undefined): string {
  return GROUPS[groupOf(aspect)].color;
}
