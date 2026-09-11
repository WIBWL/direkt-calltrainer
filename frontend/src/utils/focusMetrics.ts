/**
 * Which measured Kennzahlen stand behind a focus goal (F-62, F-13).
 *
 * The dashboard has to show something per picked goal, and the honest answer
 * differs per goal: eight of the fourteen have a measured series today, one is
 * answered by a comparison between two stretches of a call, two by activity
 * figures alone, and three have nothing but the wrap-up texts (see
 * docs/dashboard-konzept.md, section 4.2). This map is what lets the tile say
 * which of the four it is instead of rendering an empty box or inventing a
 * figure.
 *
 * A frontend map and not a database column, deliberately. It is a display
 * decision about which chart belongs on which tile; a column would make it look
 * like a property of the goal and would have to be migrated every time a metric
 * is added. When the wrap-up starts tagging its points with a goal key (the
 * concept's stage 2), the text-only goals gain their content from that, not
 * from here.
 */

/** What a focus goal can be backed by on the dashboard today.
 *
 *  `segment` is its own kind rather than a `metric` with a note, because what
 *  stands behind it is a *pair* of figures per training and not a series: it is
 *  read across the two stretches of one call, never as one line over time
 *  (ADR 0081). A chart of it would be the comparison drawn as a direction. */
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
  // Sprechtempo, Sprechpausen and how long a stretch of speech runs between
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
  // Kennzahlen over the stretches where the other side pushed back and over the
  // rest of the call (ADR 0081). The order is the order they are worth reading
  // in, and it is also the order `segments.SEGMENT_METRIC_KEYS` writes them.
  composure: {
    kind: "segment",
    metrics: ["pace", "run_length", "pauses", "loudness", "talk_share"],
  },
  // Answered by the wrap-up texts. Named individually rather than defaulted, so
  // adding a goal to the catalogue forces a decision here instead of silently
  // landing in the "no measurement" bucket.
  //
  // Articulation has a note of its own: no measurement is *planned* for it
  // either (docs/dashboard-konzept.md, section 4.2), and the wrap-up has less
  // to go on here than for the two below, where what was said is what the goal
  // is about.
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
 * The focus goals a Kennzahl stands behind, read backwards out of the map
 * above.
 *
 * For the Kennzahl's own page, which shows what the wrap-ups wrote about the
 * goals it is evidence for. Derived rather than written out a second time: two
 * hand-kept directions of the same relation drift on the first edit.
 *
 * Only the *primary* metric counts, `metrics[0]`. A goal lists every figure
 * worth looking at beside it — `active_listening` names Reaktionszeit as well
 * as Unterbrechungen — but a sentence about listening does not belong under
 * every one of them, and Reaktionszeit would collect statements from three
 * goals it is only a supporting figure for.
 */
export function goalsForMetric(metricKey: string): string[] {
  return Object.entries(FOCUS_BACKING)
    .filter(([, backing]) => backing.metrics[0] === metricKey)
    .map(([goal]) => goal);
}
