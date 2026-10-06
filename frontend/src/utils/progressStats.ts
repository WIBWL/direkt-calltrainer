import type { MetricAspect, SessionSummary } from "../protocol";
import {
  comparableAcrossCalls,
  formatValue,
  isCount,
  partsTotal,
  seriesShape,
  type SeriesShape,
} from "./metrics";

/** The history as the dashboard's series (F-13). Never a target, threshold,
 * trend line or direction (ADR 0065): this module is where one would sneak in. */

/** Two points make a line, and a line asserts a direction. */
export const MIN_SESSIONS_FOR_SERIES = 3;

/** Completed trainings only (ADR 0034). One function, or the call sites disagree (ADR 0102). */
export function completedOnly(sessions: SessionSummary[]): SessionSummary[] {
  return sessions.filter((session) => session.status === "completed");
}

/** Set, not measured: under a minute a talk share describes a fragment. On length,
 *  not status, since `aborted` also means a dropped connection. */
export const MIN_CALL_MS = 60_000;

/** Separate from `completedOnly`: a short call still counts as training, but its figures are not a series. */
export function readable(sessions: SessionSummary[]): SessionSummary[] {
  return sessions.filter((session) => {
    const ms = callDurationMs(session);
    return ms === null || ms >= MIN_CALL_MS;
  });
}

/** Spreads covered by the usual-range band (ADR 0051). */
const BAND_DEVIATION = 1;

export interface SeriesPoint {
  sessionId: string;
  at: string;
  value: number;
  scenario: string;
  persona: string;
}

export type { SeriesShape };

export interface MetricSeries {
  key: string;
  name: string;
  unit: string | null;
  /** Decides the row's group and hue (`utils/metricGroups`): identity, never a value. */
  aspect: MetricAspect | null;
  shape: SeriesShape;
  /** How the figure was derived, as a sentence; null when shown as measured. */
  derivation: string | null;
  points: SeriesPoint[];
  /** Null with too few points, and always for a `parts` series. */
  band: Band | null;
}

export interface Band {
  low: number;
  high: number;
  median: number;
}

/** Reversed once here: the history arrives newest first (ADR 0064). */
export function toSeries(sessions: SessionSummary[]): MetricSeries[] {
  const byKey = new Map<string, MetricSeries>();

  for (const session of [...sessions].reverse()) {
    for (const measurement of session.measurements) {
      if (!comparableAcrossCalls(measurement.key)) continue;

      const series = byKey.get(measurement.key) ?? {
        key: measurement.key,
        name: measurement.name,
        unit: measurement.unit,
        aspect: measurement.aspect,
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

/** The widest-banded series, when no focus goals are picked. Picks what to show, not what is better (ADR 0065). */
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

/** A checklist reads as parts "erkannt", never "2 von 3", which reads as a grade (F-63). */
export function formatPoint(series: MetricSeries, value: number): string {
  if (series.shape === "parts") {
    const count = Math.round(value);
    return `${count} ${count === 1 ? "Teil" : "Teile"} erkannt`;
  }
  return formatValue(series.key, value, series.unit);
}

/** For a count both ends are whole and clamped at zero. */
export function formatBand(series: MetricSeries): string | null {
  return series.band ? formatRange(series, series.band) : null;
}

/** One rule for every range on a screen. */
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

/** A count over a named denominator, never a share or direction. */
export function completeParts(series: MetricSeries): number | null {
  const total = partsTotal(series.key);
  if (total === null) return null;
  return series.points.filter((p) => Math.round(p.value) >= total).length;
}

/** Null where the catalogue gives no part count. */
export function partsSummary(series: MetricSeries): string | null {
  const total = partsTotal(series.key);
  const complete = completeParts(series);
  if (total === null || complete === null) return null;
  return `In ${complete} von ${series.points.length} Trainings alle ${total} Teile erkannt`;
}

/** Median ± MAD, so one unusual call does not stretch it. A description, not a target (ADR 0065). */
export function band(values: number[]): Band | null {
  if (values.length < MIN_SESSIONS_FOR_SERIES) return null;
  const middle = median(values);
  const spread = median(values.map((v) => Math.abs(v - middle)));
  // A zero MAD falls back to the mean absolute deviation.
  const width =
    spread || values.reduce((sum, v) => sum + Math.abs(v - middle), 0) / values.length;
  return {
    median: middle,
    low: middle - BAND_DEVIATION * width,
    high: middle + BAND_DEVIATION * width,
  };
}

export interface Halves {
  early: Band;
  late: Band;
  /** Always equal; see `halves`. */
  each: number;
}

/** The band over the older and newer half (ADR 0081's construction): never a
 * difference, ratio or direction (ADR 0051/0065). An odd middle is in neither. */
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
  firstAt: string | null;
  lastAt: string | null;
}

/** Activity needs no norm (ADR 0065). Completed trainings only. */
export function activity(sessions: SessionSummary[]): Activity {
  const finished = completedOnly(sessions);
  const dates = finished.map((s) => s.started_at).sort();
  return {
    sessions: finished.length,
    scenarios: new Set(finished.map((s) => s.scenario)).size,
    personas: new Set(finished.map((s) => s.persona)).size,
    firstAt: dates[0] ?? null,
    lastAt: dates[dates.length - 1] ?? null,
  };
}

/** Counted in trainings, not days: a day window is empty for anyone training in bursts. */
export function latest(sessions: SessionSummary[], count: number | null): SessionSummary[] {
  return count === null ? sessions : sessions.slice(0, count);
}

/** Null without a recorded end. Not a Measurement. */
export function callDurationMs(session: SessionSummary): number | null {
  if (!session.ended_at) return null;
  const started = new Date(session.started_at).getTime();
  const ended = new Date(session.ended_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(ended) || ended < started) return null;
  return ended - started;
}

/** The measured metrics plus the call length; the one list every progress screen reads. */
export function selectionSeries(sessions: SessionSummary[]): MetricSeries[] {
  // The length floor, applied once for both kinds of series.
  const long = readable(sessions);
  const duration = durationSeries(long);
  return [...toSeries(long), ...(duration ? [duration] : [])];
}

/** The call lengths in minutes; `derived` in `utils/metrics`, with no `metric_type` row. */
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
    aspect: "what",
    shape: "line",
    derivation: "Aus Beginn und Ende des Gesprächs gerechnet, nicht aus der Aufnahme.",
    points,
    band: band(points.map((p) => p.value)),
  };
}

export interface ActivityDay {
  date: string;
  dayOfMonth: number;
  /** Completed only: the calendar answers "when did I train". */
  count: number;
}

export interface ActivityMonth {
  label: string;
  year: number;
  month: number;
  /** Monday first; `null` pads the first and last week. */
  weeks: (ActivityDay | null)[][];
  total: number;
}

/** Three steps: one person's volume has no more values than that. */
export type ActivityStep = 0 | 1 | 2 | 3;

export function activityStep(count: number): ActivityStep {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  return 3;
}

/** One month, Monday first. The period switch does not reach it. */
export function activityMonth(
  sessions: SessionSummary[],
  year: number,
  month: number,
): ActivityMonth {
  const counts = trainingDays(sessions);
  const lastDay = new Date(year, month + 1, 0).getDate();
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

/** Abandoned calls are left out here, so no view can count them back in. */
function trainingDays(sessions: SessionSummary[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const session of completedOnly(sessions)) {
    const key = dayKey(new Date(session.started_at));
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

/** As far back as paging makes sense. Null with nothing stored. */
export function firstTrainingMonth(
  sessions: SessionSummary[],
): { year: number; month: number } | null {
  let oldest: number | null = null;
  for (const session of completedOnly(sessions)) {
    const at = new Date(session.started_at).getTime();
    if (Number.isNaN(at)) continue;
    if (oldest === null || at < oldest) oldest = at;
  }
  if (oldest === null) return null;
  const date = new Date(oldest);
  return { year: date.getFullYear(), month: date.getMonth() };
}

/** Local time: `toISOString` would shift a late-evening training into the next day east of UTC. */
export function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

/** Keyed by the same `dayKey` as the shading, so the list matches the cell. */
export function trainingsOn(sessions: SessionSummary[], date: Date): SessionSummary[] {
  const key = dayKey(date);
  return completedOnly(sessions).filter(
    (session) => dayKey(new Date(session.started_at)) === key,
  );
}

/** Through the same `completedOnly`, so a cell saying 2 never opens onto three rows. */
export function trainingsWith(
  sessions: SessionSummary[],
  scenario: string,
  persona: string,
): SessionSummary[] {
  return completedOnly(sessions).filter(
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

/** Played combinations only: empty cells would read as a to-do list. */
export function variety(sessions: SessionSummary[]): Variety {
  const counts = new Map<string, VarietyCell>();
  for (const session of completedOnly(sessions)) {
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

/** Most played first, alphabetical on a tie. */
function byFrequency(cells: VarietyCell[], name: (cell: VarietyCell) => string): string[] {
  const totals = new Map<string, number>();
  for (const cell of cells) totals.set(name(cell), (totals.get(name(cell)) ?? 0) + cell.count);
  return [...totals.entries()]
    .sort(([a, x], [b, y]) => y - x || a.localeCompare(b, "de"))
    .map(([key]) => key);
}
