import type { SessionSummary } from "../protocol";

/**
 * Turning the training history into the series the dashboard draws
 * (F-13, docs/dashboard-konzept.md).
 *
 * Pure functions over what `GET /api/sessions` already returns, deliberately:
 * every value here was measured server-side and stored with its Session
 * (ADR 0051). Nothing in this module derives a new figure about the user, it
 * only groups measured ones by metric and describes their spread.
 *
 * What it must never grow: a target, a threshold, a trend line or a direction.
 * ADR 0065 rules those out for exactly this view, and the place they would
 * sneak in is here, as a helper nobody reviewed.
 */

/** Below this a series is noise: two points make a line, and a line asserts a
 *  direction. The dashboard shows single values instead and says so. */
export const MIN_SESSIONS_FOR_SERIES = 3;

/** How many multiples of the spread the usual-range band covers. The same
 *  construction backend/feedback/metrics.py uses for the loudness course, and
 *  self-referential for the same reason (ADR 0051). */
const BAND_DEVIATION = 1;

export interface SeriesPoint {
  sessionId: string;
  /** ISO 8601, the Session's start. */
  at: string;
  value: number;
  scenario: string;
  persona: string;
}

export interface MetricSeries {
  key: string;
  /** The German display name, straight from `metric_type.name`. */
  name: string;
  unit: string | null;
  /** Oldest first, so the chart reads left to right in time. */
  points: SeriesPoint[];
  /** The user's own usual range, or null with too few points to describe one. */
  band: Band | null;
}

export interface Band {
  low: number;
  high: number;
  median: number;
}

/**
 * One series per metric, oldest point first.
 *
 * The history arrives newest first (ADR 0064); a chart reads the other way, so
 * the reversal happens once, here, rather than in each component.
 */
export function toSeries(sessions: SessionSummary[]): MetricSeries[] {
  const byKey = new Map<string, MetricSeries>();

  for (const session of [...sessions].reverse()) {
    for (const measurement of session.measurements) {
      // Retired metric types are left out. A Session measured before a metric
      // was renamed points at the old row, which carries the same display name
      // as the new one, so keeping both would draw two charts called
      // "Redeanteil" side by side. Merging them is not an option either: the
      // definitions changed with ADR 0051, and splicing two different
      // measurements into one line would be the quiet kind of wrong.
      if (!measurement.active) continue;
      const series = byKey.get(measurement.key) ?? {
        key: measurement.key,
        name: measurement.name,
        unit: measurement.unit,
        points: [],
        band: null,
      };
      series.points.push({
        sessionId: session.session_id,
        at: session.started_at,
        value: measurement.value,
        scenario: session.scenario,
        persona: session.persona,
      });
      byKey.set(measurement.key, series);
    }
  }

  for (const series of byKey.values()) {
    series.band = band(series.points.map((p) => p.value));
  }
  return [...byKey.values()];
}

/**
 * The range the user held for most of their trainings: their median, widened by
 * their own spread.
 *
 * Median absolute deviation rather than a standard deviation, so one unusual
 * call does not stretch the band around every other one. Null below the series
 * threshold: a "usual range" over two values describes nothing.
 *
 * This is a description of the data, not a target. Nothing may colour a value
 * by whether it falls inside (ADR 0065).
 */
export function band(values: number[]): Band | null {
  if (values.length < MIN_SESSIONS_FOR_SERIES) return null;
  const middle = median(values);
  const spread = median(values.map((v) => Math.abs(v - middle)));
  // A zero MAD means more than half the values are identical; the mean absolute
  // deviation still separates them, and only a constant series has neither.
  const width =
    spread || values.reduce((sum, v) => sum + Math.abs(v - middle), 0) / values.length;
  return {
    median: middle,
    low: middle - BAND_DEVIATION * width,
    high: middle + BAND_DEVIATION * width,
  };
}

export function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2
    : (sorted[middle] ?? 0);
}

/** Rounded the way the value is worth reading: a Redeanteil of 46.3 % is 46 %,
 *  a Reaktionszeit of 1.84 s is 1.8 s. Chosen by magnitude rather than per
 *  metric, so a new metric needs no entry anywhere. */
export function formatValue(value: number, unit: string | null): string {
  const decimals = Math.abs(value) >= 20 ? 0 : 1;
  const text = value.toFixed(decimals).replace(".", ",");
  return unit ? `${text} ${unit}` : text;
}

export interface Activity {
  sessions: number;
  scenarios: number;
  personas: number;
  /** ISO 8601 of the oldest and newest training in the set, or null when empty. */
  firstAt: string | null;
  lastAt: string | null;
}

/** What the user did, counted. Activity needs no norm to be shown, which is
 *  what ADR 0065 names as explicitly permitted. */
export function activity(sessions: SessionSummary[]): Activity {
  const dates = sessions.map((s) => s.started_at).sort();
  return {
    sessions: sessions.length,
    scenarios: new Set(sessions.map((s) => s.scenario)).size,
    personas: new Set(sessions.map((s) => s.persona)).size,
    firstAt: dates[0] ?? null,
    lastAt: dates[dates.length - 1] ?? null,
  };
}

/** Sessions inside the selected period. `null` days means everything that is
 *  still stored, which after six months is all there is (ADR 0067). */
export function withinPeriod(sessions: SessionSummary[], days: number | null): SessionSummary[] {
  if (days === null) return sessions;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return sessions.filter((s) => new Date(s.started_at).getTime() >= cutoff);
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** How long the call ran, in minutes, or null where it has no recorded end.
 *
 * Derived from the two timestamps rather than measured, which is why it is not
 * a Measurement: it belongs to the same family as the activity figures, it
 * describes what happened rather than how it was spoken, and it needs no norm
 * to be worth showing.
 */
export function durationMinutes(session: SessionSummary): number | null {
  if (!session.ended_at) return null;
  const started = new Date(session.started_at).getTime();
  const ended = new Date(session.ended_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(ended) || ended < started) return null;
  return (ended - started) / 60000;
}

/** The call lengths as a series, so they can be drawn like any Kennzahl. */
export function durationSeries(sessions: SessionSummary[]): MetricSeries | null {
  const points: SeriesPoint[] = [];
  for (const session of [...sessions].reverse()) {
    const minutes = durationMinutes(session);
    if (minutes === null) continue;
    points.push({
      sessionId: session.session_id,
      at: session.started_at,
      value: minutes,
      scenario: session.scenario,
      persona: session.persona,
    });
  }
  if (points.length === 0) return null;
  return {
    key: "duration",
    name: "Gesprächsdauer",
    unit: "min",
    points,
    band: band(points.map((p) => p.value)),
  };
}

export interface ActivityBucket {
  /** Start of the bucket, ISO 8601. */
  from: string;
  /** What the axis calls it, already formatted for German readers. */
  label: string;
  completed: number;
  aborted: number;
}

/**
 * Trainings per time bucket, for the activity chart.
 *
 * Counting is all this does, and counting needs no norm: ADR 0065 names
 * activity figures as explicitly permitted, because they say what the user did
 * rather than how well they did it. Abandoned calls are counted separately and
 * not hidden. That is a fact about the training, not a mark against it, and the
 * history already states it the same way.
 *
 * The bucket width follows the span so the chart keeps a readable number of
 * bars: days for a month, weeks for half a year, months beyond that.
 */
export function activityBuckets(sessions: SessionSummary[], days: number | null): ActivityBucket[] {
  if (sessions.length === 0) return [];

  const times = sessions.map((s) => new Date(s.started_at).getTime()).sort((a, b) => a - b);
  const firstTime = times[0] ?? Date.now();
  const spanDays = days ?? Math.max(1, (Date.now() - firstTime) / MS_PER_DAY);
  const unit: "day" | "week" | "month" =
    spanDays <= 35 ? "day" : spanDays <= 210 ? "week" : "month";

  const start = startOf(days === null ? new Date(firstTime) : new Date(Date.now() - days * MS_PER_DAY), unit);
  const buckets: ActivityBucket[] = [];
  for (let at = new Date(start); at <= new Date(); at = next(at, unit)) {
    buckets.push({ from: at.toISOString(), label: labelOf(at, unit), completed: 0, aborted: 0 });
  }
  // A period with no training at all still gets one bucket, so the chart has an
  // axis rather than collapsing to nothing.
  if (buckets.length === 0) {
    buckets.push({
      from: start.toISOString(),
      label: labelOf(start, unit),
      completed: 0,
      aborted: 0,
    });
  }

  for (const session of sessions) {
    const at = startOf(new Date(session.started_at), unit).getTime();
    const bucket = buckets.find((b) => new Date(b.from).getTime() === at);
    if (!bucket) continue;
    if (session.status === "aborted") bucket.aborted += 1;
    else bucket.completed += 1;
  }
  return buckets;
}

function startOf(date: Date, unit: "day" | "week" | "month"): Date {
  const out = new Date(date);
  out.setHours(0, 0, 0, 0);
  if (unit === "week") {
    // Monday, because a German week starts there and the labels say "KW".
    const weekday = (out.getDay() + 6) % 7;
    out.setDate(out.getDate() - weekday);
  }
  if (unit === "month") out.setDate(1);
  return out;
}

function next(date: Date, unit: "day" | "week" | "month"): Date {
  const out = new Date(date);
  if (unit === "day") out.setDate(out.getDate() + 1);
  if (unit === "week") out.setDate(out.getDate() + 7);
  if (unit === "month") out.setMonth(out.getMonth() + 1);
  return out;
}

function labelOf(date: Date, unit: "day" | "week" | "month"): string {
  if (unit === "month") {
    return date.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
  }
  return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
}

export interface VarietyCell {
  scenario: string;
  persona: string;
  count: number;
}

export interface Variety {
  scenarios: string[];
  personas: string[];
  cells: VarietyCell[];
}

/**
 * Which Scenario the user played against which Persona, and how often.
 *
 * Only combinations that actually occurred, deliberately. A grid of everything
 * the library offers with the unplayed cells left empty would turn a
 * description of what someone did into a list of what they have not done yet,
 * and nothing here is a task anybody set them.
 */
export function variety(sessions: SessionSummary[]): Variety {
  const counts = new Map<string, VarietyCell>();
  for (const session of sessions) {
    const id = `${session.scenario} ${session.persona}`;
    const cell = counts.get(id) ?? { scenario: session.scenario, persona: session.persona, count: 0 };
    cell.count += 1;
    counts.set(id, cell);
  }
  const cells = [...counts.values()];
  return {
    scenarios: [...new Set(cells.map((c) => c.scenario))].sort(),
    personas: [...new Set(cells.map((c) => c.persona))].sort(),
    cells,
  };
}
