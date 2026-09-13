import type { Measurement, MetricAspect, TrafficLight } from "../protocol";

/**
 * How the call's statistics (F-53) are labelled, split and read.
 *
 * Shared rather than owned by the feedback page, because the downloadable
 * report (`utils/feedbackPdf.ts`) and the progress view read the same figures:
 * a tile saying "2,4" on screen and "2.4 Sekunden" in the file would be the
 * same measurement reported twice, differently.
 *
 * Never a judgement, only a reading — ADR 0051 declined to invent the norms
 * that would be needed to say whether a figure is good, which is what
 * `METRIC_DISCLAIMER` says wherever they are shown.
 */

/**
 * Every metric the backend measures today, as its own type.
 *
 * Hand-written, and pinned to the backend inventory by a test
 * (`tests/test_metrics.py`): adding a metric there fails the suite until it is
 * described here. That is the whole point of the union — the catalogue below
 * is keyed by it, so a missing entry is a compile error rather than a figure
 * that quietly renders as "4.0" on one screen and vanishes from another.
 */
export type MetricKey =
  | "talk_share"
  | "questions"
  | "pace"
  | "word_count"
  | "fillers"
  | "opening"
  | "closing"
  | "repetitions"
  | "hesitations"
  | "reaction_time"
  | "pauses"
  | "phonation_share"
  | "run_length"
  | "loudness"
  | "intonation"
  | "interruptions";

/** `line` is every ordinary metric: a value per training, a course, a band.
 * `parts` is a checklist, drawn as marks rather than a line — a course of
 * 1-3-2-3 over a band reads as a score climbing to full marks, which is the
 * reading ADR 0086 kept off the single call's tile. */
export type SeriesShape = "line" | "parts";

interface MetricDescriptor {
  /**
   * Whether the figure means anything set beside another call's.
   *
   * Required, with no default: it used to be absence from a `NOT_ACROSS_CALLS`
   * set, so a new metric was silently comparable. The loudness is the one that
   * is not — its dB span is the microphone and the distance as much as the
   * speaker (ADR 0076's amendment).
   */
  comparableAcrossCalls: boolean;
  /**
   * Whether it earns a row in the progress overview.
   *
   * Required for the same reason: it used to be absence from a hidden-set.
   * A metric can be worth measuring and still repeat what the row above it
   * already said.
   */
  inOverview: boolean;
  /** Decimals the figure reads naturally in. Defaults to none for a count and
   * one otherwise, which is right for every metric that omits it. */
  decimals?: number;
  /**
   * A checklist's parts, in the order they are usually said (F-63, ADR 0089).
   *
   * The tile, the progress view and the PDF all show *which* parts from this
   * one list: "1 von 3" was not self-explanatory in the first test and read
   * like a mark (ADR 0004).
   */
  parts?: readonly (readonly [key: string, label: string])[];
  /**
   * How many parts one call can be credited with — deliberately not
   * `parts.length`. The opening lists four but checks three: the offer of help
   * and the concern depend on who rang, so exactly one of them applies. This
   * number used to be read out of the unit string `"von 3"` with a regex.
   */
  partsTotal?: number;
  /** What the tile's drill-down promises, where it has one. */
  openHint?: string;
}

/**
 * One row per metric, and the only place a metric's display facts live.
 *
 * Private on purpose: callers ask the functions below rather than indexing
 * this, so the table can grow a field without every screen learning about it.
 */
const CATALOGUE: Record<MetricKey, MetricDescriptor> = {
  talk_share: { comparableAcrossCalls: true, inOverview: true, decimals: 0 },
  questions: { comparableAcrossCalls: true, inOverview: true },
  pace: { comparableAcrossCalls: true, inOverview: true, decimals: 0 },
  // Across trainings this repeats the call length in other units. Still
  // measured, and still reachable from its own page and the concise-speech goal.
  word_count: { comparableAcrossCalls: true, inOverview: false, decimals: 0 },
  fillers: { comparableAcrossCalls: true, inOverview: true },
  opening: {
    comparableAcrossCalls: true,
    inOverview: true,
    decimals: 0,
    parts: [
      ["greeting", "Begrüßung"],
      ["name", "Name"],
      ["offer", "Hilfsangebot"],
      ["concern", "Anliegen"],
    ],
    partsTotal: 3,
  },
  closing: {
    comparableAcrossCalls: true,
    inOverview: true,
    decimals: 0,
    parts: [
      ["recap", "Zusammenfassung"],
      ["agreement", "Vereinbarung"],
      ["farewell", "Verabschiedung"],
    ],
    partsTotal: 3,
  },
  repetitions: { comparableAcrossCalls: true, inOverview: true },
  hesitations: { comparableAcrossCalls: true, inOverview: true },
  reaction_time: { comparableAcrossCalls: true, inOverview: true },
  pauses: { comparableAcrossCalls: true, inOverview: true },
  phonation_share: { comparableAcrossCalls: true, inOverview: true, decimals: 0 },
  run_length: { comparableAcrossCalls: true, inOverview: true },
  // The one metric that is not comparable between calls; see the field above.
  loudness: { comparableAcrossCalls: false, inOverview: true },
  intonation: {
    comparableAcrossCalls: true,
    inOverview: true,
    openHint: "Diese Kennzahl ansehen",
  },
  interruptions: {
    comparableAcrossCalls: true,
    inOverview: true,
    openHint: "Einzelne Stellen ansehen",
  },
};

/**
 * What a key the catalogue has never been taught reads as.
 *
 * Reachable for a renamed metric: the detail route serves a stored Session's
 * measurements unfiltered, so a call from before ADR 0057's rename still
 * carries `redeanteil`. It renders plainly rather than crashing. The progress
 * views never see one — they drop anything the backend marks inactive.
 */
const UNKNOWN: MetricDescriptor = { comparableAcrossCalls: true, inOverview: true };

/** The unit the backend gives a plain count. Shown without the word, since
 * "4 Anzahl" says less than "4" beside a name that already has it. */
const COUNT_UNIT = "Anzahl";

function describe(key: string): MetricDescriptor {
  return CATALOGUE[key as MetricKey] ?? UNKNOWN;
}

/** Whether a unit counts things, and so reads in whole numbers. */
export function isCount(unit: string | null | undefined): boolean {
  return unit === COUNT_UNIT;
}

export interface MetricPart {
  key: string;
  label: string;
  /** Recognised. The absence of a match is not proof of an absence — a bare
   * name or a recap worded some other way slips past the patterns — so the
   * other state reads "not recognised", never "missing". */
  said: boolean;
}

/** Whether this metric is drawn as a checklist or as a figure over time. */
export function seriesShape(key: string): SeriesShape {
  return describe(key).parts ? "parts" : "line";
}

/** How many parts one call can be credited with, or null for a figure. */
export function partsTotal(key: string): number | null {
  return describe(key).partsTotal ?? null;
}

/** Whether the figure may be set beside another call's (F-13, ADR 0065). */
export function comparableAcrossCalls(key: string): boolean {
  return describe(key).comparableAcrossCalls;
}

/** Whether it earns a row in the progress overview. */
export function showsInOverview(key: string): boolean {
  return describe(key).inOverview;
}

/** What the tile's drill-down promises. */
export function openHint(key: string): string {
  return describe(key).openHint ?? "Ansehen";
}

/** The parts a checklist metric checked, in order, or null for any other
 * metric. Only the parts the detail actually carries: the opening checks
 * either the offer or the concern, never both. */
export function metricParts(measurement: Measurement): MetricPart[] | null {
  const parts = describe(measurement.key).parts;
  if (!parts) return null;
  const detail = measurement.detail ?? {};
  return parts
    .filter(([key]) => key in detail)
    .map(([key, label]) => ({ key, label, said: detail[key] === true }));
}

/**
 * The reading a metric carries beside its figure, where it carries one —
 * F-51's traffic light and F-35's three-step liveliness (ADR 0077, ADR 0078).
 *
 * Every part is served by the backend beside the threshold it was read off
 * (`api/sessions.py::_served_detail`), so a recalibration cannot leave a stale
 * word or colour on screen; this only says where in `detail` each one sits,
 * once for the tile and the metric's own page.
 */
export interface MetricReading {
  /** The step in words, e.g. "lebendig". */
  label: string | undefined;
  /** The step's machine name, to mark it on the scale (`MetricScale`). */
  step: string | undefined;
  /** The colour of the figure itself. F-51's only: F-35's step is read off the
   * liveliness, not off the range its figure shows, and a green semitone count
   * would be a colour over something it was not read from. */
  figureLight: TrafficLight | undefined;
  /** The colour of the step in words. */
  readingLight: TrafficLight | undefined;
}

export function metricReading(measurement: Measurement): MetricReading {
  const detail = measurement.detail ?? {};
  const light = detail["light"] as TrafficLight | undefined;
  return {
    label: (detail["light_label"] ?? detail["liveliness_label"]) as string | undefined,
    step: (detail["liveliness"] ?? light) as string | undefined,
    figureLight: light,
    readingLight: (detail["liveliness_light"] ?? light) as TrafficLight | undefined,
  };
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

/**
 * One figure as it is read out, for every screen that shows one.
 *
 * The single rule. There used to be three — this one keyed by metric, one in
 * `progressStats` keyed by magnitude, and a third parsing the unit string —
 * and they disagreed: the same reaction time read "1.8 s" on the wrap-up and
 * "1,8 s" on the progress table. The comma is the German one and the dot was
 * simply wrong.
 *
 * `unit` is passed rather than looked up because the caller sometimes has a
 * reason to suppress it: the low end of a range carries no unit, the high end
 * does.
 */
export function formatValue(key: string, value: number, unit: string | null): string {
  const decimals = describe(key).decimals ?? (isCount(unit) ? 0 : 1);
  const text = value.toFixed(decimals).replace(".", ",");
  return unit && !isCount(unit) ? `${text} ${unit}` : text;
}

/** The same rule, for a whole Measurement. */
export function formatMetricValue(measurement: Measurement): string {
  return formatValue(measurement.key, measurement.value, measurement.unit);
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
