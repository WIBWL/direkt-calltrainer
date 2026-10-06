/** Which metrics stand behind a focus goal (F-62, F-13). A frontend map: which chart goes on which tile is display. */

/** `segment` is a pair per training (ADR 0081), never a series: a line would draw it as a direction. */
export type FocusEvidenceKind = "metric" | "activity" | "text" | "segment";

export interface FocusBacking {
  kind: FocusEvidenceKind;
  /** Most telling first. */
  metrics: string[];
  /** Only for "text". */
  note?: string;
}

const NO_MEASUREMENT =
  "Zu diesem Ziel gibt es noch keine Messung. Was dazu gesagt werden kann, " +
  "steht in den Auswertungen Ihrer einzelnen Gespräche.";

/** ADR 0085. */
export const NO_VALUE_YET =
  "Zu diesem Ziel wird gemessen, aber in den ausgewählten Trainings liegt dazu " +
  "kein Wert vor, weil sie sich darin nicht messen ließ.";

export const FOCUS_BACKING: Record<string, FocusBacking> = {
  // Together they are the rhythm; each alone can stay flat while it moves.
  pace: { kind: "metric", metrics: ["pace", "pauses", "run_length"] },
  talk_share: { kind: "metric", metrics: ["talk_share"] },
  needs_analysis: { kind: "metric", metrics: ["questions", "talk_share"] },
  // Interruptions first: the most direct trace of listening.
  active_listening: { kind: "metric", metrics: ["interruptions", "reaction_time", "pauses"] },
  // Word count last: it grows with the call.
  conciseness: {
    kind: "metric",
    metrics: ["fillers", "hesitations", "repetitions", "word_count"],
  },
  intonation: { kind: "metric", metrics: ["intonation"] },
  opening: { kind: "metric", metrics: ["opening"] },
  // ADR 0089; whether the close was clear is still the wrap-up's.
  closing: { kind: "metric", metrics: ["closing"] },
  training_regularity: { kind: "activity", metrics: [] },
  training_variety: { kind: "activity", metrics: [] },
  // Answered by a comparison (ADR 0081), in `segments.SEGMENT_METRIC_KEYS` order.
  composure: {
    kind: "segment",
    metrics: ["pace", "run_length", "pauses", "loudness", "talk_share"],
  },
  // Named one by one, so a new catalogue goal forces a decision here.
  objection_handling: { kind: "text", metrics: [], note: NO_MEASUREMENT },
  empathy: { kind: "text", metrics: [], note: NO_MEASUREMENT },
};

export function backingOf(goalKey: string): FocusBacking {
  return FOCUS_BACKING[goalKey] ?? { kind: "text", metrics: [], note: NO_MEASUREMENT };
}

/** Only the primary metric counts, or a supporting one collects every goal's statements. */
export function goalsForMetric(metricKey: string): string[] {
  return Object.entries(FOCUS_BACKING)
    .filter(([, backing]) => backing.metrics[0] === metricKey)
    .map(([goal]) => goal);
}
