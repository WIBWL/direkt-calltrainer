import type { Measurement, MetricAspect, TrafficLight } from "../protocol";

/** How a metric is labelled, split and read on every screen and in the PDF. No norms (ADR 0051). */

/** Pinned to the backend inventory by shared/tests/test_metrics.py, so an undescribed metric fails to compile. */
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
  | "interruptions"
  /** The call length, derived in the browser; added by hand, the test checks only the other direction. */
  | "duration";

/** `parts` is a checklist, drawn as marks: a 1-3-2-3 line reads as a climbing score (ADR 0086). */
export type SeriesShape = "line" | "parts";

interface MetricDescriptor {
  /** Required, so a new metric is never silently comparable. Loudness is not (ADR 0076). */
  comparableAcrossCalls: boolean;
  /** Worked out in the browser, with no `metric_type` row; kept out of `METRIC_KEYS`. */
  derived?: boolean;
  inOverview: boolean;
  /** Defaults to none for a count and one otherwise. */
  decimals?: number;
  /** A checklist's parts (F-63, ADR 0089); screens name which, since "1 von 3" reads like a mark. */
  parts?: readonly (readonly [key: string, label: string])[];
  /** Not `parts.length`: the opening lists four but checks three. */
  partsTotal?: number;
  openHint?: string;
}

/** Private: callers use the functions below, so a new field reaches no screen by accident. */
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
  // Across trainings this repeats the call length, so no overview row.
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
  // Derived, not measured; the context every count needs.
  duration: {
    derived: true,
    comparableAcrossCalls: true,
    inOverview: true,
    decimals: 0,
    openHint: "Die einzelnen Gespräche ansehen",
  },
};

/** Every metric a call can carry, so a screen can notice one not taken. */
export const METRIC_KEYS = (Object.keys(CATALOGUE) as MetricKey[]).filter(
  (key) => !CATALOGUE[key].derived,
);

/** An unknown key renders plainly rather than crashing. */
const UNKNOWN: MetricDescriptor = { comparableAcrossCalls: true, inOverview: true };

/** Shown without the word: "4 Anzahl" says less than "4". */
const COUNT_UNIT = "Anzahl";

function describe(key: string): MetricDescriptor {
  return CATALOGUE[key as MetricKey] ?? UNKNOWN;
}

export function isCount(unit: string | null | undefined): boolean {
  return unit === COUNT_UNIT;
}

export interface MetricPart {
  key: string;
  label: string;
  /** No match is not proof of absence, so the other state reads "not recognised". */
  said: boolean;
}

export function seriesShape(key: string): SeriesShape {
  return describe(key).parts ? "parts" : "line";
}

export function partsTotal(key: string): number | null {
  return describe(key).partsTotal ?? null;
}

/** F-13, ADR 0065. */
export function comparableAcrossCalls(key: string): boolean {
  return describe(key).comparableAcrossCalls;
}

export function showsInOverview(key: string): boolean {
  return describe(key).inOverview;
}

export function openHint(key: string): string {
  return describe(key).openHint ?? "Ansehen";
}

/** Only the parts the detail carries: the opening checks the offer or the concern. */
export function metricParts(measurement: Measurement): MetricPart[] | null {
  const parts = describe(measurement.key).parts;
  if (!parts) return null;
  const detail = measurement.detail ?? {};
  return parts
    .filter(([key]) => key in detail)
    .map(([key, label]) => ({ key, label, said: detail[key] === true }));
}

/** F-51's light, F-35's liveliness (ADR 0077, 0078): served beside the threshold, never mapped here. */
export interface MetricReading {
  label: string | undefined;
  step: string | undefined;
  /** F-51's only: F-35's step is not read off the range its figure shows. */
  figureLight: TrafficLight | undefined;
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

export const METRIC_ASPECTS: MetricAspect[] = ["how", "what"];

export const ASPECT_LABELS: Record<MetricAspect, string> = {
  how: "Wie Sie gesprochen haben",
  what: "Was Sie gesagt haben",
};

export const ASPECT_LEADS: Record<MetricAspect, string> = {
  how: "Ihre Sprechweise: Tempo, Pausen, Lautstärke und wie schnell Sie geantwortet haben.",
  what:
    "Der Zuschnitt des Gesprächs: wie viel Raum Sie eingenommen und wie viel Sie " +
    "gefragt haben.",
};

/** Wherever a figure is, on screen and in the file (ADR 0004/0051). */
export const METRIC_DISCLAIMER =
  "Reine Messwerte, ohne Zielbereich: Für diese Nutzergruppe gibt es keinen belegten " +
  "Normwert, an dem sie zu messen wären.";

/** Anything unclassified falls to `what`, so it still gets a tile. */
export function metricAspect(measurement: Measurement): MetricAspect {
  return measurement.aspect === "how" ? "how" : "what";
}

/** Plus the one derived from another (`sentenceLength`). */
export function withDerived(measurements: Measurement[]): Measurement[] {
  const derived = sentenceLength(measurements);
  return derived ? [...measurements, derived] : measurements;
}

/** For figures that belong to no metric; a metric's value goes through `formatValue`. */
export function formatNumber(value: number, decimals: number): string {
  return value.toFixed(decimals).replace(".", ",");
}

/** The single formatting rule, with the German comma. */
export function formatValue(key: string, value: number, unit: string | null): string {
  const decimals = describe(key).decimals ?? (isCount(unit) ? 0 : 1);
  const text = formatNumber(value, decimals);
  return unit && !isCount(unit) ? `${text} ${unit}` : text;
}

export function formatMetricValue(measurement: Measurement): string {
  return formatValue(measurement.key, measurement.value, measurement.unit);
}

/** Where `detail` refines the same figure. */
export function metricSubline(measurement: Measurement): string | null {
  if (measurement.key === "fillers") {
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
  // On the tile itself: this one is a detection.
  if (measurement.key === "hesitations") return "geschätzt aus der Tonhöhe";
  if (measurement.key !== "questions") return null;
  const open = measurement.detail?.["open"];
  const closed = measurement.detail?.["closed"];
  if (typeof open !== "number" || typeof closed !== "number") return null;
  return `davon ${open} offen, ${closed} geschlossen`;
}

/** The opening's tempo against the rest of the User's own call (F-63). */
function openingSubline(measurement: Measurement): string | null {
  const ratio = measurement.detail?.["pace_ratio"];
  if (typeof ratio !== "number") return null;
  const percent = Math.round((ratio - 1) * 100);
  return `Einstieg ${Math.abs(percent)} % ${percent >= 0 ? "schneller" : "langsamer"} als sonst`;
}

/** Where the closing was looked for (ADR 0089), so a recap said too early can be seen as why. */
function closingSubline(measurement: Measurement): string | null {
  const read = measurement.detail?.["turns_read"];
  if (typeof read !== "number") return null;
  return `geprüft: ${read === 1 ? "Ihr letzter Beitrag" : `Ihre letzten ${read} Beiträge`}`;
}

/** F-08's second half, from `word_count`'s `detail`, rather than a second stored row. */
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
