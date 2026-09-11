import type { MetricAspect, SessionSummary } from "../protocol";

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
  /** Which half of the Kennzahlen this one belongs to, from the schema's own
   *  column. It decides the side of the dashboard's switch and the hue the
   *  chart is drawn in (`utils/metricGroups`) — identity, never a value. */
  aspect: MetricAspect | null;
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
        aspect: measurement.aspect,
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
  const cutoff = Date.now() - days * MS_PER_DAY;
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
    // `what`, like the docstring above argues: it describes what happened
    // rather than how somebody spoke. Written here rather than read off the
    // wire because this one is the exception that has no `metric_type` row.
    aspect: "what",
    points,
    band: band(points.map((p) => p.value)),
  };
}

/** One day of the calendar, whether or not anything happened on it. */
export interface ActivityDay {
  /** Local midnight of the day, ISO 8601. */
  date: string;
  /** Day of the month, which is what the cell prints when nothing happened. */
  dayOfMonth: number;
  /** Completed trainings on that day. An abandoned call is not counted and not
   *  marked either: the calendar answers "when did I train", and a call that
   *  broke off is not an answer to it. */
  count: number;
}

/** One month of the calendar, its days padded to whole weeks. */
export interface ActivityMonth {
  /** "September 2026", for the heading. */
  label: string;
  year: number;
  /** 0-11, as `Date` counts them. */
  month: number;
  /** Whole weeks, Monday first. `null` pads the first and last week, so a
   *  month always renders as a rectangle and the weekday columns line up. */
  weeks: (ActivityDay | null)[][];
  /** Trainings in this month, for the heading's own count. */
  total: number;
}

/** The step a day's cell is shaded at. Three, not seven: at the volume one
 *  person trains at, a day holds one, two or a handful of calls, and a ramp
 *  with more steps than the data has values encodes nothing. */
export type ActivityStep = 0 | 1 | 2 | 3;

export function activityStep(count: number): ActivityStep {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  return 3;
}

/**
 * One calendar month, Monday-first, with each day's trainings on it.
 *
 * A calendar rather than a bar per day: the question this block answers is "when
 * did I train", and on a calendar the answer includes the shape of a week —
 * whether the trainings sit on workdays, whether a fortnight went by. A bar
 * chart has the same numbers and none of that.
 *
 * One month at a time, and the month is the caller's to choose. The period
 * switch above the dashboard says which trainings the Kennzahlen are read over;
 * a calendar already carries its own range in the grid, so letting the switch
 * cut months off it would be the same statement twice, the second time as a
 * missing chunk of a chart.
 *
 * Counting what somebody did needs no norm, which is why this is the one block
 * on the screen that carries no caveat (ADR 0065).
 */
export function activityMonth(
  sessions: SessionSummary[],
  year: number,
  month: number,
): ActivityMonth {
  const counts = trainingDays(sessions);
  const lastDay = new Date(year, month + 1, 0).getDate();
  // Monday first, because a German week starts there.
  const lead = (new Date(year, month, 1).getDay() + 6) % 7;

  const cells: (ActivityDay | null)[] = Array(lead).fill(null);
  let total = 0;
  for (let day = 1; day <= lastDay; day += 1) {
    const date = new Date(year, month, day);
    const count = counts.get(dayKey(date)) ?? 0;
    total += count;
    cells.push({ date: date.toISOString(), dayOfMonth: day, count });
  }
  while (cells.length % 7 !== 0) cells.push(null);

  const weeks: (ActivityDay | null)[][] = [];
  for (let at = 0; at < cells.length; at += 7) weeks.push(cells.slice(at, at + 7));

  return {
    label: new Date(year, month, 1).toLocaleDateString("de-DE", {
      month: "long",
      year: "numeric",
    }),
    year,
    month,
    weeks,
    total,
  };
}

/** How many completed trainings fell on each day. Abandoned calls are left out
 *  entirely, here and not in the component, so no view can count them back in. */
function trainingDays(sessions: SessionSummary[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const session of sessions) {
    if (session.status !== "completed") continue;
    const key = dayKey(new Date(session.started_at));
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

/** The month the oldest training falls in, which is as far back as paging makes
 *  sense: earlier months are empty by definition (ADR 0067 caps them at six
 *  anyway). Null with nothing stored. */
export function firstTrainingMonth(
  sessions: SessionSummary[],
): { year: number; month: number } | null {
  let oldest: number | null = null;
  for (const session of sessions) {
    if (session.status !== "completed") continue;
    const at = new Date(session.started_at).getTime();
    if (Number.isNaN(at)) continue;
    if (oldest === null || at < oldest) oldest = at;
  }
  if (oldest === null) return null;
  const date = new Date(oldest);
  return { year: date.getFullYear(), month: date.getMonth() };
}

/** A day as a key, in local time. Built from the parts rather than from
 *  `toISOString`, which would shift a late-evening training into the next day
 *  for anybody east of UTC. */
function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
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
