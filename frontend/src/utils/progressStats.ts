import type { MetricAspect, SessionSummary } from "../protocol";
import {
  comparableAcrossCalls,
  formatValue,
  isCount,
  partsTotal,
  seriesShape,
  type SeriesShape,
} from "./metrics";

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

/** How a series is drawn; decided by `utils/metrics`, which knows which
 * metrics are checklists. */
export type { SeriesShape };

export interface MetricSeries {
  key: string;
  /** The German display name, straight from `metric_type.name`. */
  name: string;
  unit: string | null;
  /** Which half of the metrics this one belongs to, from the schema's own
   *  column. It decides the group the row sits in and the hue the chart is
   *  drawn in (`utils/metricGroups`) — identity, never a value. */
  aspect: MetricAspect | null;
  shape: SeriesShape;
  /** How the figure was derived from the stored one, where it was, as a
   *  sentence for the reader. Null for a value shown exactly as measured. */
  derivation: string | null;
  /** Oldest first, so the chart reads left to right in time. */
  points: SeriesPoint[];
  /** The user's own usual range, or null with too few points to describe one
   *  and always null for a `parts` series. */
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
      // "talk share" side by side. Merging them is not an option either: the
      // definitions changed with ADR 0051, and splicing two different
      // measurements into one line would be the quiet kind of wrong.
      if (!measurement.active) continue;
      if (!comparableAcrossCalls(measurement.key)) continue;

      const series = byKey.get(measurement.key) ?? {
        key: measurement.key,
        name: measurement.name,
        unit: measurement.unit,
        aspect: measurement.aspect,
        // From the same catalogue the single call's tile reads, so a
        // checklist cannot be a checklist on one screen and a climbing
        // line on the other.
        shape: seriesShape(measurement.key),
        derivation: null,
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
    series.band = series.shape === "line" ? band(series.points.map((p) => p.value)) : null;
  }
  return [...byKey.values()];
}

/**
 * One value of a series as the reader should see it.
 *
 * The same as `formatValue` for an ordinary metric. A checklist is written
 * out as how many parts were recognised, never as "2 von 3": that fraction is
 * what reads as a grade, and "erkannt" keeps it a detection, which is all it
 * is -- a bare name slips past the patterns (F-63).
 */
export function formatPoint(series: MetricSeries, value: number): string {
  if (series.shape === "parts") {
    const count = Math.round(value);
    return `${count} ${count === 1 ? "Teil" : "Teile"} erkannt`;
  }
  return formatValue(series.key, value, series.unit);
}

/**
 * The user's usual range in words, or null where there is none to describe.
 *
 * For a count the two ends are whole numbers, and never below zero: the band is
 * a median widened by a spread, which around a median of 0 or 1 reaches past
 * zero on paper, and "-0,5 bis 1,5 Unterbrechungen" describes nothing anybody
 * did. Where both ends round to the same number the range is that number.
 */
export function formatBand(series: MetricSeries): string | null {
  if (!series.band) return null;
  if (isCount(series.unit)) {
    const low = Math.max(0, Math.round(series.band.low));
    const high = Math.max(low, Math.round(series.band.high));
    return low === high ? `meist ${low}` : `${low} bis ${high}`;
  }
  return (
    `${formatValue(series.key, series.band.low, null)} bis ` +
    `${formatValue(series.key, series.band.high, series.unit)}`
  );
}

/** In how many trainings every part of a checklist was recognised. A count of
 *  trainings over a named denominator, the same kind of statement as the
 *  recurring block's count over a named denominator, never a share or a
 *  direction. */
export function completeParts(series: MetricSeries): number | null {
  const total = partsTotal(series.key);
  if (total === null) return null;
  return series.points.filter((p) => Math.round(p.value) >= total).length;
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

/**
 * The most recent `count` trainings, or all of them for `null`.
 *
 * Counted in trainings rather than in days. Somebody who trains in bursts --
 * three calls before an appointment, then nothing for a month -- finds a
 * 30-day window empty half the time, and an empty dashboard teaches that there
 * is nothing here; "the last five" is never empty while anything is stored,
 * and it is also the unit the metrics are read in, one point per training.
 * The history arrives newest first (ADR 0064), so this is a slice. `null`
 * means everything still stored, which is at most six months (ADR 0067).
 */
export function latest(sessions: SessionSummary[], count: number | null): SessionSummary[] {
  return count === null ? sessions : sessions.slice(0, count);
}

/** How long the call ran, in milliseconds, or null where it has no recorded end
 * — which a Session cut short by a pipeline failure legitimately may not.
 *
 * Derived from the two timestamps rather than measured, which is why it is not
 * a Measurement: it belongs to the same family as the activity figures, it
 * describes what happened rather than how it was spoken, and it needs no norm
 * to be worth showing. The history's rows show the same length as mm:ss.
 */
export function callDurationMs(session: SessionSummary): number | null {
  if (!session.ended_at) return null;
  const started = new Date(session.started_at).getTime();
  const ended = new Date(session.ended_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(ended) || ended < started) return null;
  return ended - started;
}

/** The call lengths as a series, in minutes, so they can be drawn like any
 *  metric. */
export function durationSeries(sessions: SessionSummary[]): MetricSeries | null {
  const points: SeriesPoint[] = [];
  for (const session of [...sessions].reverse()) {
    const ms = callDurationMs(session);
    if (ms === null) continue;
    points.push({
      sessionId: session.session_id,
      at: session.started_at,
      value: ms / 60000,
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
    shape: "line",
    derivation: "Aus Beginn und Ende des Gesprächs gerechnet, nicht aus der Aufnahme.",
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
 * switch, which stands below the calendar, says which trainings the metrics
 * are read over;
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
 *  for anybody east of UTC. The calendar marks today with the same key, so
 *  "is this cell today" cannot answer differently than the shading. */
export function dayKey(date: Date): string {
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
    const id = `${session.scenario}\0${session.persona}`;
    const cell = counts.get(id) ?? { scenario: session.scenario, persona: session.persona, count: 0 };
    cell.count += 1;
    counts.set(id, cell);
  }
  const cells = [...counts.values()];
  return {
    scenarios: byFrequency(cells, (c) => c.scenario),
    personas: byFrequency(cells, (c) => c.persona),
    cells,
  };
}

/**
 * The distinct names along one side of the grid, most played first.
 *
 * Frequency first because the grid is cut after a few rows (`VarietyGrid`), and
 * what the reader should see before the show-more button is where their training has
 * actually gone. Alphabetical on a tie, so the order does not shuffle between
 * two loads of the same data.
 */
function byFrequency(cells: VarietyCell[], name: (cell: VarietyCell) => string): string[] {
  const totals = new Map<string, number>();
  for (const cell of cells) totals.set(name(cell), (totals.get(name(cell)) ?? 0) + cell.count);
  return [...totals.entries()]
    .sort(([a, x], [b, y]) => y - x || a.localeCompare(b, "de"))
    .map(([key]) => key);
}
