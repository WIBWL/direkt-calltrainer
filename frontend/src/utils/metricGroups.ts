import type { MetricAspect } from "../protocol";

/** A metric's family and hue (F-13): identity, never judgement (ADR 0065). Red,
 * amber and green belong to ADR 0078's traffic light. Validated as a set of three. */

export type MetricGroup = "speech" | "content" | "activity";

export interface GroupStyle {
  label: string;
  /** A custom property from index.css. */
  color: string;
}

export const GROUPS: Record<MetricGroup, GroupStyle> = {
  // Nearest the application's navy.
  speech: { label: "Sprechweise", color: "var(--series-speech)" },
  content: { label: "Gesprächsinhalt", color: "var(--series-content)" },
  // Never returned by `groupOf`; declared to keep the validated set together.
  activity: { label: "Aktivität", color: "var(--series-activity)" },
};

/** From the served `metric_type.aspect`; none falls to `speech`, as on the backend. */
export function groupOf(aspect: MetricAspect | null | undefined): MetricGroup {
  return aspect === "what" ? "content" : "speech";
}

export function colorOf(aspect: MetricAspect | null | undefined): string {
  return GROUPS[groupOf(aspect)].color;
}
