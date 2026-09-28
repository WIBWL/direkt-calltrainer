/**
 * Which metrics stand behind a focus goal (F-62, F-13), so a tile names its kind
 * of evidence instead of inventing a figure (docs/dashboard-concept.md, 4.2).
 * A frontend map, not a column: which chart goes on which tile is display.
 */

/** What a focus goal can be backed by on the dashboard today. `segment` is a
 *  pair of figures per training (two stretches of one call, ADR 0081), never a
 *  series: a line over time would draw the comparison as a direction. */
export type FocusEvidenceKind = "metric" | "activity" | "text" | "segment";

export interface FocusBacking {
  kind: FocusEvidenceKind;
  /** Metric keys, most telling first. Empty unless `kind` is "metric". */
  metrics: string[];
  /** Why there is no chart, shown on the tile. Only for "text". */
  note?: string;
}

const NO_MEASUREMENT =
  "Zu diesem Ziel gibt es noch keine Messung. Was dazu gesagt werden kann, " +
  "steht in den Auswertungen Ihrer einzelnen Gespräche.";

const NO_MEASUREMENT_PLANNED =
  "Zu diesem Ziel gibt es keine Messung, und es ist keine geplant: Wie deutlich " +
  "jemand spricht, hängt am Aufnahmegerät genauso wie an der Person. Was dazu " +
  "gesagt werden kann, steht in den Auswertungen Ihrer einzelnen Gespräche.";

export const FOCUS_BACKING: Record<string, FocusBacking> = {
  // speaking pace, pauses and how long a stretch of speech runs between
  // them. The three together are the rhythm of somebody's speaking; each on
  // its own can look unchanged while the rhythm moves.
  pace: { kind: "metric", metrics: ["pace", "pauses", "run_length"] },
  talk_share: { kind: "metric", metrics: ["talk_share"] },
  needs_analysis: { kind: "metric", metrics: ["questions", "talk_share"] },
  // Interruptions first: how often somebody let the other side finish is the
  // most direct trace of listening the call leaves behind.
  active_listening: { kind: "metric", metrics: ["interruptions", "reaction_time", "pauses"] },
  // Word count last: it grows with the call, not with how concise it was.
  conciseness: {
    kind: "metric",
    metrics: ["fillers", "hesitations", "repetitions", "word_count"],
  },
  intonation: { kind: "metric", metrics: ["intonation"] },
  opening: { kind: "metric", metrics: ["opening"] },
  // Its counterpart at the other end of the call (ADR 0089): recap, next step,
  // goodbye, counted in the last two turns. It moved out of the text-only group
  // below; whether the close was *clear* is still what the wrap-up says, and
  // the goal's own page quotes that under the parts.
  closing: { kind: "metric", metrics: ["closing"] },
  training_regularity: { kind: "activity", metrics: [] },
  training_variety: { kind: "activity", metrics: [] },
  // The one goal answered by a comparison rather than by a figure: the same
  // metrics over the stretches where the other side pushed back and over the
  // rest of the call (ADR 0081). The order is the order they are worth reading
  // in, and it is also the order `segments.SEGMENT_METRIC_KEYS` writes them.
  composure: {
    kind: "segment",
    metrics: ["pace", "run_length", "pauses", "loudness", "talk_share"],
  },
  // Answered by the wrap-up texts. Named individually, not defaulted, so a new
  // catalogue goal forces a decision here. Articulation has no measurement
  // planned either (docs/dashboard-concept.md, section 4.2).
  articulation: { kind: "text", metrics: [], note: NO_MEASUREMENT_PLANNED },
  objection_handling: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  empathy: { kind: "text", metrics: [], note: NO_MEASUREMENT },
};

/** The backing of one goal, or the honest fallback for a goal this map has not
 *  been told about yet. */
export function backingOf(goalKey: string): FocusBacking {
  return FOCUS_BACKING[goalKey] ?? { kind: "text", metrics: [], note: NO_MEASUREMENT };
}

/**
 * The focus goals a metric stands behind, derived from the map above. Only the
 * primary metric (`metrics[0]`) counts, or a supporting figure such as reaction
 * time would collect the statements of every goal that merely lists it.
 */
export function goalsForMetric(metricKey: string): string[] {
  return Object.entries(FOCUS_BACKING)
    .filter(([, backing]) => backing.metrics[0] === metricKey)
    .map(([goal]) => goal);
}
