/**
 * Which measured Kennzahlen stand behind a focus goal (F-62, F-13).
 *
 * The dashboard has to show something per picked goal, and the honest answer
 * differs per goal: nine of the fifteen have measurements today, two are
 * answered by activity figures alone, and four have nothing but the wrap-up
 * texts (see docs/dashboard-konzept.md, section 4.2). This map is what lets the
 * tile say which of the three it is instead of rendering an empty box or
 * inventing a figure.
 *
 * A frontend map and not a database column, deliberately. It is a display
 * decision about which chart belongs on which tile; a column would make it look
 * like a property of the goal and would have to be migrated every time a metric
 * is added. When the wrap-up starts tagging its points with a goal key (the
 * concept's stage 2), the text-only goals gain their content from that, not
 * from here.
 */

/** What a focus goal can be backed by on the dashboard today. */
export type FocusEvidenceKind = "metric" | "activity" | "text";

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

export const FOCUS_BACKING: Record<string, FocusBacking> = {
  pace: { kind: "metric", metrics: ["pace", "pauses"] },
  loudness: { kind: "metric", metrics: ["loudness"] },
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
  training_regularity: { kind: "activity", metrics: [] },
  training_variety: { kind: "activity", metrics: [] },
  // No measurement yet. Named individually rather than defaulted, so adding a
  // goal to the catalogue forces a decision here instead of silently landing in
  // the "no measurement" bucket.
  articulation: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  composure: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  opening: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  objection_handling: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  closing: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  empathy: { kind: "text", metrics: [], note: NO_MEASUREMENT },
};

/** The backing of one goal, or the honest fallback for a goal this map has not
 *  been told about yet. */
export function backingOf(goalKey: string): FocusBacking {
  return FOCUS_BACKING[goalKey] ?? { kind: "text", metrics: [], note: NO_MEASUREMENT };
}
