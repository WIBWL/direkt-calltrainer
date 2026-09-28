import type { MetricAspect } from "../protocol";

/** A metric's family and its colour (F-13): identity, never judgement (ADR 0065).
 * Nothing here takes a value, so a figure cannot move a colour, and red, amber and
 * green are reserved for ADR 0078's traffic light. Palette slots 1, 5 and 7,
 * validated as a set of three (CVD ΔE 13.0); a hue per metric would not separate. */

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
  // Slot 7, violet. `groupOf` never returns it (the activity charts read
  // `--series-activity` directly); declared here so the validated set of three
  // stays together.
  activity: { label: "Aktivität", color: "var(--series-activity)" },
};

/**
 * The family of one metric, from the served `metric_type.aspect` (assigned in
 * `backend/feedback/metrics.py`). No aspect falls to `speech`, matching the
 * backend's fallback.
 */
export function groupOf(aspect: MetricAspect | null | undefined): MetricGroup {
  return aspect === "what" ? "content" : "speech";
}

/** The hue of one metric, for a chart mark. */
export function colorOf(aspect: MetricAspect | null | undefined): string {
  return GROUPS[groupOf(aspect)].color;
}
