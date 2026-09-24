import type { MetricAspect, SessionSummary } from "../protocol";
import {
  comparableAcrossCalls,
  formatValue,
  isCount,
  partsTotal,
  seriesShape,
  type SeriesShape,
} from "./metrics";

/** The training history as the dashboard's series (F-13, docs/dashboard-concept.md):
 * pure functions that group server-measured figures (ADR 0051) and describe their
 * spread. Must never grow a target, threshold, trend line or direction (ADR 0065)
 * — this module is where one would sneak in. */

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
 * One series per metric, oldest point first: the history arrives newest first
 * (ADR 0064), so it is reversed once, here, rather than in each component.
 */
export function toSeries(sessions: SessionSummary[]): MetricSeries[] {
  const byKey = new Map<string, MetricSeries>();

  for (const session of [...sessions].reverse()) {
    for (const measurement of session.measurements) {
      // Retired metric types are left out: a renamed metric's old row shares the
      // display name and would draw a duplicate chart, and merging is wrong
      // since the definitions changed with ADR 0051.
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

/** The series that moved most, widest first, standing in for focus goals when none
 * are picked. Band width relative to its middle, so units compare; it picks what to
 * show, not what is better (ADR 0065). Only series with a band count. */
export function mostVarying(series: MetricSeries[], count: number): MetricSeries[] {
  return series
    .filter((s) => s.points.length >= MIN_SESSIONS_FOR_SERIES && s.band !== null)
    .map((s) => ({ s, spread: relativeSpread(s.band as Band) }))
    .sort((a, b) => b.spread - a.spread)
    .slice(0, count)
    .map(({ s }) => s);
}

function relativeSpread(range: Band): number {
  return (range.high - range.low) / (Math.abs(range.median) || 1);
}

/**
 * One value of a series as the reader should see it. A checklist reads as parts
 * "erkannt", never "2 von 3", which reads as a grade (F-63).
 */
export function formatPoint(series: MetricSeries, value: number): string {
  if (series.shape === "parts") {
    const count = Math.round(value);
    return `${count} ${count === 1 ? "Teil" : "Teile"} erkannt`;
  }
  return formatValue(series.key, value, series.unit);
}

/**
 * The user's usual range in words, or null. For a count both ends are whole and
 * clamped at zero ("-0,5 bis 1,5 Unterbrechungen" describes nothing anybody did).
 */
export function formatBand(series: MetricSeries): string | null {
  return series.band ? formatRange(series, series.band) : null;
}

/** The same, for a band that is not the series' own — the two halves below.
 *  One rule, so an earlier range and the overall one cannot round or punctuate
 *  differently on the same screen. */
export function formatRange(series: MetricSeries, range: Band): string {
  if (isCount(series.unit)) {
    const low = Math.max(0, Math.round(range.low));
    const high = Math.max(low, Math.round(range.high));
    return low === high ? `meist ${low}` : `${low} bis ${high}`;
  }
  return (
    `${formatValue(series.key, range.low, null)} bis ` +
    `${formatValue(series.key, range.high, series.unit)}`
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

/** A checklist's sentence: in how many trainings every part was recognised. Null
 * where the catalogue gives no part count. Here, not in `PartsStrip.tsx`, because
 * three screens and the progress PDF say it. */
export function partsSummary(series: MetricSeries): string | null {
  const total = partsTotal(series.key);
  const complete = completeParts(series);
  if (total === null || complete === null) return null;
  return `In ${complete} von ${series.points.length} Trainings alle ${total} Teile erkannt`;
}

/** The user's usual range: median ± MAD, so one unusual call does not stretch it.
 * Null below the series threshold. A description, not a target: nothing may colour
 * a value by whether it falls inside (ADR 0065). */
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

/** The user's earlier trainings and their recent ones, each described on its
 *  own terms. */
export interface Halves {
  early: Band;
  late: Band;
  /** How many trainings each half holds. Always equal — see `halves`. */
  each: number;
}

/** The band over the older and the newer half of the selection (concept, section
 * 8's amendment; ADR 0081's construction). Two bands only: never a difference,
 * ratio or direction (ADR 0051/0065). Equal halves; an odd middle is in neither.
 * Null below twice the series threshold. */
export function halves(series: MetricSeries): Halves | null {
  if (series.shape !== "line") return null;
  const each = Math.floor(series.points.length / 2);
  if (each < MIN_SESSIONS_FOR_SERIES) return null;

  const values = series.points.map((point) => point.value);
  const early = band(values.slice(0, each));
  const late = band(values.slice(-each));
  if (!early || !late) return null;
  return { early, late, each };
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

/** The most recent `count` trainings, or all for `null` (at most six months, ADR
 * 0067). Counted in trainings, not days, because a day window is empty for anyone
 * training in bursts. The history is newest first (ADR 0064), so this is a slice. */
export function latest(sessions: SessionSummary[], count: number | null): SessionSummary[] {
  return count === null ? sessions : sessions.slice(0, count);
}

/** How long the call ran in ms, from its two timestamps, or null where it has no
 * recorded end (a Session cut short by a pipeline failure). Not a Measurement:
 * it describes what happened, like the activity figures. */
export function callDurationMs(session: SessionSummary): number | null {
  if (!session.ended_at) return null;
  const started = new Date(session.started_at).getTime();
  const ended = new Date(session.ended_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(ended) || ended < started) return null;
  return ended - started;
}

/** Every series of a selection: the measured metrics plus the call length. The one
 * list all progress screens read (via `ProgressContext`), so every row the overview
 * links to exists on the page behind the link. */
export function selectionSeries(sessions: SessionSummary[]): MetricSeries[] {
  const duration = durationSeries(sessions);
  return [...toSeries(sessions), ...(duration ? [duration] : [])];
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

/** One calendar month, Monday-first, with each day's trainings; the month is the
 * caller's. A calendar shows the shape of a week, which bars do not. The period
 * switch deliberately does not reach it: the grid carries its own range. Counting
 * needs no norm, so it carries no caveat (ADR 0065). */
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

/** The trainings behind one calendar cell, newest first. Completed only and keyed
 * by the same `dayKey` as the shading, so the list always matches the number the
 * cell prints. */
export function trainingsOn(sessions: SessionSummary[], date: Date): SessionSummary[] {
  const key = dayKey(date);
  return sessions.filter(
    (session) =>
      session.status === "completed" && dayKey(new Date(session.started_at)) === key,
  );
}

/** The trainings behind one cell of the variety grid, newest first. No status
 *  filter, because `variety` counts every stored training into the cell and the
 *  list has to match what the cell says. */
export function trainingsWith(
  sessions: SessionSummary[],
  scenario: string,
  persona: string,
): SessionSummary[] {
  return sessions.filter(
    (session) => session.scenario === scenario && session.persona === persona,
  );
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
 * Which Scenario was played against which Persona, and how often. Played
 * combinations only: empty cells would read as a to-do list.
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
 * The distinct names along one side of the grid, most played first (the grid is
 * cut after a few rows, `VarietyGrid`), alphabetical on a tie for a stable order.
 */
function byFrequency(cells: VarietyCell[], name: (cell: VarietyCell) => string): string[] {
  const totals = new Map<string, number>();
  for (const cell of cells) totals.set(name(cell), (totals.get(name(cell)) ?? 0) + cell.count);
  return [...totals.entries()]
    .sort(([a, x], [b, y]) => y - x || a.localeCompare(b, "de"))
    .map(([key]) => key);
}
