import type { Measurement, MetricAspect } from "../protocol";

/**
 * How the call's statistics (F-53) are labelled, split and read.
 *
 * Shared rather than owned by the feedback page, because the downloadable
 * report (`utils/feedbackPdf.ts`) carries the same figures: a tile saying
 * "2,4" on screen and "2.4 Sekunden" in the file would be the same measurement
 * reported twice, differently.
 *
 * Never a judgement, only a reading — ADR 0051 declined to invent the norms
 * that would be needed to say whether a figure is good, which is what
 * `METRIC_DISCLAIMER` says wherever they are shown.
 */

/** How many decimals a metric reads naturally in. Counts are whole things;
 * seconds and percentages are not. */
const DECIMALS: Record<string, number> = {
  questions: 0, word_count: 0, pace: 0, talk_share: 0, phonation_share: 0,
};

/** The two halves (backend/db/models.py METRIC_ASPECTS), in slider order. */
export const METRIC_ASPECTS: MetricAspect[] = ["how", "what"];

export const ASPECT_LABELS: Record<MetricAspect, string> = {
  how: "Wie Sie gesprochen haben",
  what: "Was Sie gesagt haben",
};

/** One line under the slider saying what the half in view is a reading of. */
export const ASPECT_LEADS: Record<MetricAspect, string> = {
  how: "Ihre Sprechweise: Tempo, Pausen, Lautstärke und wie schnell Sie geantwortet haben.",
  what:
    "Der Zuschnitt des Gesprächs: wie viel Raum Sie eingenommen und wie viel Sie " +
    "gefragt haben.",
};

/** Said wherever a figure is, on screen and in the file (ADR 0004/0051). */
export const METRIC_DISCLAIMER =
  "Reine Messwerte, ohne Zielbereich: für diese Nutzergruppe gibt es keinen belegten " +
  "Normwert, an dem sie zu messen wären.";

/** `how` is the closed side; everything else falls to `what`, so an
 * unclassified metric still gets a tile. */
export function metricAspect(measurement: Measurement): MetricAspect {
  return measurement.aspect === "how" ? "how" : "what";
}

/** The measured figures plus the one that is derived from another (see
 * `sentenceLength`), which is what both renderers actually show. */
export function withDerived(measurements: Measurement[]): Measurement[] {
  const derived = sentenceLength(measurements);
  return derived ? [...measurements, derived] : measurements;
}

/** The figure as it is read out: value at its own precision, and the unit
 * where the unit says something. "Anzahl" does not — the name already has it. */
export function formatMetricValue(measurement: Measurement): string {
  const decimals = DECIMALS[measurement.key] ?? 1;
  const unit =
    measurement.unit && measurement.unit !== "Anzahl" ? ` ${measurement.unit}` : "";
  return `${measurement.value.toFixed(decimals)}${unit}`;
}

/** A second line under a metric's value, where its `detail` refines the same
 * figure rather than standing beside it. Absent for a call whose language has
 * no question words on file. */
export function metricSubline(measurement: Measurement): string | null {
  if (measurement.key !== "questions") return null;
  const open = measurement.detail?.["open"];
  const closed = measurement.detail?.["closed"];
  if (typeof open !== "number" || typeof closed !== "number") return null;
  return `davon ${open} offen, ${closed} geschlossen`;
}

/** The loudness curve out of a Measurement's `detail` (ADR 0029), or null. It
 * is the only thing that metric has to show: its value is a dB span that reads
 * like a level without being one (ADR 0004/0051). */
export function loudnessCurve(measurement: Measurement): (number | null)[] | null {
  const curve = measurement.detail?.["curve_db"] as (number | null)[] | undefined;
  if (!curve?.some((value) => value !== null)) return null;
  return curve;
}

/** F-08's second half, already in `word_count`'s own `detail`: its own tile,
 * because the two answer different questions, but not its own metric_type row
 * — that would store one number twice. */
function sentenceLength(measurements: Measurement[]): Measurement | null {
  const words = measurements.find((m) => m.key === "word_count");
  const value = words?.detail?.["words_per_sentence"];
  if (typeof value !== "number") return null;
  return {
    key: "words_per_sentence",
    name: "Wörter pro Satz",
    unit: null,
    aspect: "what",
    value,
    detail: null,
  };
}
