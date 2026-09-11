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
  questions: 0, word_count: 0, pace: 0, talk_share: 0, phonation_share: 0, fillers: 0,
  repetitions: 0, hesitations: 0, opening: 0, closing: 0,
};

/**
 * The checklist Kennzahlen and their parts, in the order they are usually
 * said: the opening (F-63, ADR 0086) and the closing (ADR 0089).
 *
 * Their value is how many parts were recognised, and none of the three places
 * that show them leads with that number. "1 von 3" was not self-explanatory in
 * the first test and read like a mark (ADR 0004), so the tile, the progress
 * view and the PDF all show *which* parts, from this one list.
 *
 * The opening's third part depends on who rang, and a stored call carries
 * whichever was checked; the ones stored before the split carry "concern".
 */
const METRIC_PARTS: Record<string, [key: string, label: string][]> = {
  opening: [
    ["greeting", "Begrüßung"],
    ["name", "Name"],
    ["offer", "Hilfsangebot"],
    ["concern", "Anliegen"],
  ],
  closing: [
    ["recap", "Zusammenfassung"],
    ["agreement", "Vereinbarung"],
    ["farewell", "Verabschiedung"],
  ],
};

export interface MetricPart {
  key: string;
  label: string;
  /** Recognised. The absence of a match is not proof of an absence — a bare
   * name or a recap worded some other way slips past the patterns — so the
   * other state is "nicht erkannt", never "fehlt". */
  said: boolean;
}

/** Whether this Kennzahl is a checklist rather than a figure. */
export function isPartsMetric(key: string): boolean {
  return key in METRIC_PARTS;
}

/** The parts a checklist Kennzahl checked, in order, or null for any other
 * Kennzahl. Only the parts the detail actually carries: the opening checks
 * either the offer or the concern, never both. */
export function metricParts(measurement: Measurement): MetricPart[] | null {
  const parts = METRIC_PARTS[measurement.key];
  if (!parts) return null;
  const detail = measurement.detail ?? {};
  return parts
    .filter(([key]) => key in detail)
    .map(([key, label]) => ({ key, label, said: detail[key] === true }));
}

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
  "Reine Messwerte, ohne Zielbereich: Für diese Nutzergruppe gibt es keinen belegten " +
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
 * no word list on file. */
export function metricSubline(measurement: Measurement): string | null {
  if (measurement.key === "fillers") {
    // Most frequent first, in the order the backend's `most_common` wrote them.
    const words = measurement.detail?.["words"] as Record<string, number> | undefined;
    const top = Object.entries(words ?? {}).slice(0, 2);
    if (top.length === 0) return null;
    return "meist " + top.map(([word, n]) => `„${word}“ (${n}×)`).join(", ");
  }
  if (measurement.key === "repetitions") {
    const passages = measurement.detail?.["passages"] as string[] | undefined;
    const first = passages?.[0];
    if (!first) return null;
    const words = first.split(" ");
    return `z. B. „${words.slice(0, 6).join(" ")}${words.length > 6 ? " …" : ""}“`;
  }
  if (measurement.key === "opening") return openingSubline(measurement);
  if (measurement.key === "closing") return closingSubline(measurement);
  // Said on the tile itself, not only on a page: this one is a detection.
  if (measurement.key === "hesitations") return "geschätzt aus der Tonhöhe";
  if (measurement.key !== "questions") return null;
  const open = measurement.detail?.["open"];
  const closed = measurement.detail?.["closed"];
  if (typeof open !== "number" || typeof closed !== "number") return null;
  return `davon ${open} offen, ${closed} geschlossen`;
}

/** "33 % langsamer als sonst" — the opening's tempo against the rest of the
 *  User's own call; the parts themselves are the headline (F-63). */
function openingSubline(measurement: Measurement): string | null {
  const ratio = measurement.detail?.["pace_ratio"];
  if (typeof ratio !== "number") return null;
  const percent = Math.round((ratio - 1) * 100);
  return `Einstieg ${Math.abs(percent)} % ${percent >= 0 ? "schneller" : "langsamer"} als sonst`;
}

/** Where the closing was looked for (ADR 0089), with the backend's own number:
 * a recap said three turns before the end was not read, and a reader who knows
 * they gave one should be able to see why it went unrecognised. */
function closingSubline(measurement: Measurement): string | null {
  const read = measurement.detail?.["turns_read"];
  if (typeof read !== "number") return null;
  return `geprüft: ${read === 1 ? "Ihr letzter Beitrag" : `Ihre letzten ${read} Beiträge`}`;
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
