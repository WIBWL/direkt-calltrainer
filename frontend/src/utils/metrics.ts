import type { Measurement, MetricAspect, TrafficLight } from "../protocol";

/**
 * How the call's statistics (F-53) are labelled, split and read — shared by the
 * page, the PDF and the progress view so a figure reads the same everywhere.
 * Never a judgement: there are no norms (ADR 0051, `METRIC_DISCLAIMER`).
 */

/**
 * Every metric the backend measures, pinned to its inventory by
 * `tests/test_metrics.py`. The catalogue below is keyed by it, so an
 * undescribed metric is a compile error rather than a silently wrong figure.
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
   * Whether the figure means anything beside another call's. Required, no default,
   * so a new metric is never silently comparable. Loudness is not: its dB span
   * depends on the microphone (ADR 0076's amendment).
   */
  comparableAcrossCalls: boolean;
  /**
   * Whether it earns a row in the progress overview. Required for the same
   * reason; a metric can be worth measuring yet repeat the row above it.
   */
  inOverview: boolean;
  /** Decimals the figure reads naturally in. Defaults to none for a count and
   * one otherwise, which is right for every metric that omits it. */
  decimals?: number;
  /**
   * A checklist's parts, in the order they are usually said (F-63, ADR 0089).
   * Every screen names *which* parts from this list; "1 von 3" read like a mark.
   */
  parts?: readonly (readonly [key: string, label: string])[];
  /**
   * How many parts one call can be credited with — not `parts.length`: the
   * opening lists four but checks three (offer of help or concern, by who rang).
   */
  partsTotal?: number;
  /** What the tile's drill-down promises, where it has one. */
  openHint?: string;
}

/**
 * One row per metric, the only place its display facts live. Private: callers
 * use the functions below, so a new field reaches no screen by accident.
 */
const CATALOGUE: Record<MetricKey, MetricDescriptor> = {
  talk_share: {
    comparableAcrossCalls: true,
    inOverview: true,
    decimals: 0,
    openHint: "Die Verteilung ansehen",
  },
  questions: { comparableAcrossCalls: true, inOverview: true, openHint: "Ihre Fragen ansehen" },
  pace: {
    comparableAcrossCalls: true,
    inOverview: true,
    decimals: 0,
    openHint: "Diese Kennzahl ansehen",
  },
  // Across trainings this repeats the call length in other units. Still
  // measured, and still reachable from its own page and the concise-speech goal.
  word_count: {
    comparableAcrossCalls: true,
    inOverview: false,
    decimals: 0,
    openHint: "Die Verteilung ansehen",
  },
  fillers: { comparableAcrossCalls: true, inOverview: true, openHint: "Die Wörter ansehen" },
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
    openHint: "Ihren Einstieg ansehen",
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
    openHint: "Ihren Abschluss ansehen",
  },
  repetitions: {
    comparableAcrossCalls: true,
    inOverview: true,
    openHint: "Die Passagen ansehen",
  },
  hesitations: {
    comparableAcrossCalls: true,
    inOverview: true,
    openHint: "Diese Kennzahl ansehen",
  },
  reaction_time: {
    comparableAcrossCalls: true,
    inOverview: true,
    openHint: "Diese Kennzahl ansehen",
  },
  pauses: { comparableAcrossCalls: true, inOverview: true, openHint: "Die Pausen ansehen" },
  phonation_share: {
    comparableAcrossCalls: true,
    inOverview: true,
    decimals: 0,
    openHint: "Die Verteilung ansehen",
  },
  run_length: {
    comparableAcrossCalls: true,
    inOverview: true,
    openHint: "Diese Kennzahl ansehen",
  },
  // The one metric that is not comparable between calls; see the field above.
  loudness: {
    comparableAcrossCalls: false,
    inOverview: true,
    openHint: "Den Verlauf groß ansehen",
  },
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
 * Every metric the catalogue knows, in inventory order, so a screen can notice
 * a measurement that could not be taken (it leaves no row at all).
 */
export const METRIC_KEYS = Object.keys(CATALOGUE) as MetricKey[];

/**
 * An unknown key, rendered plainly rather than crashing: the detail route serves
 * old Sessions unfiltered, so a pre-ADR 0057 call still carries `redeanteil`.
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

/** What the tile's drill-down promises. Every catalogue metric names its own;
 * the fallback is for an unknown key (see `UNKNOWN`). */
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
 * The reading beside a figure — F-51's traffic light, F-35's liveliness (ADR 0077,
 * ADR 0078). Word and colour are served beside the threshold, never mapped here;
 * this only says where in `detail` each sits.
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
 * A bare number with a German decimal comma, for figures that belong to no
 * metric (a semitone span, a range in an aria-label). A metric's own value goes
 * through `formatValue`.
 */
export function formatNumber(value: number, decimals: number): string {
  return value.toFixed(decimals).replace(".", ",");
}

/**
 * One figure as it is read out — the single formatting rule for every screen,
 * with the German comma. `unit` is passed so a caller can suppress it (the low
 * end of a range carries none).
 */
export function formatValue(key: string, value: number, unit: string | null): string {
  const decimals = describe(key).decimals ?? (isCount(unit) ? 0 : 1);
  const text = formatNumber(value, decimals);
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
