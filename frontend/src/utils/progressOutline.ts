import type { FocusGoal, SessionSummary } from "../protocol";
import { backingOf, NO_VALUE_YET } from "./focusMetrics";
import {
  mentionSummary,
  mentionsFor,
  statementsFor,
  type GoalStatement,
} from "./goalMentions";
import { formatBand, formatPoint, type MetricSeries } from "./progressStats";
import { segmentTrainings } from "./segmentStats";

/** What the progress report claims, for the screen and the PDF alike (F-13, ADR 0102). Pure. */

export type FocusReading =
  | {
      kind: "metric";
      series: MetricSeries;
      /** Null for no points, which `no-value` covers. */
      last: string | null;
      /** Never a target (ADR 0051). */
      band: string | null;
      trainings: number;
      /** Either a younger metric or a noisy recording; the interface claims neither. */
      missing: number;
      /** Already filtered to what a cross-call view may show. */
      supporting: MetricSeries[];
    }
  /** Measured, but nothing in this selection carries it. */
  | { kind: "no-value"; note: string }
  /** ADR 0081. */
  | { kind: "segment"; trainings: number }
  | { kind: "activity"; goal: string }
  /** `measured`: only a goal with no measurement at all may say "keine Messung". */
  | {
      kind: "mentions";
      strengths: number;
      improvements: number;
      total: number;
      latest: GoalStatement | null;
      note: string;
      measured: boolean;
    };

export interface FocusOutline {
  key: string;
  title: string;
  reading: FocusReading;
}

export interface RecurringEntry {
  goal: string;
  /** Null for a retired goal (ADR 0076); nothing may link to it. */
  title: string | null;
  count: number;
}

export interface RecurringOutline {
  strengths: RecurringEntry[];
  improvements: RecurringEntry[];
  /** The denominator, named wherever a count appears (ADR 0080). */
  total: number;
}

export interface ProgressOutlineInput {
  goals: FocusGoal[];
  series: MetricSeries[];
  /** What mention counts are read over, whatever the call length. */
  selected: SessionSummary[];
  /** The denominator behind "aus N Trainings". */
  readable: SessionSummary[];
  /** Handed in, so this module never knows why a metric is hidden. */
  shows: (key: string) => boolean;
}

/** A third would turn the tile into the table below it. */
const MAX_SUPPORTING = 2;

/** Nothing is dropped: a vanished tile lets the user believe the goal is tracked. */
export function focusOutline(input: ProgressOutlineInput): FocusOutline[] {
  return input.goals.map((goal) => ({
    key: goal.key,
    title: goal.title,
    reading: readingFor(goal, input),
  }));
}

/** Shared with the overview, so the same metric reads in the same sentences. */
export function metricReading(
  series: MetricSeries,
  readableCount: number,
  supporting: MetricSeries[] = [],
): Extract<FocusReading, { kind: "metric" }> {
  const last = series.points[series.points.length - 1];
  return {
    kind: "metric",
    series,
    last: last ? formatPoint(series, last.value) : null,
    band: formatBand(series),
    trainings: series.points.length,
    missing: Math.max(0, readableCount - series.points.length),
    supporting,
  };
}

function readingFor(goal: FocusGoal, input: ProgressOutlineInput): FocusReading {
  const { series, selected, readable, shows } = input;
  const backing = backingOf(goal.key);

  if (backing.kind === "activity") return { kind: "activity", goal: goal.key };
  if (backing.kind === "segment") {
    return { kind: "segment", trainings: segmentTrainings(selected).length };
  }

  if (backing.kind === "metric") {
    const primary = series.find((s) => s.key === backing.metrics[0]);
    if (primary) {
      return metricReading(
        primary,
        readable.length,
        backing.metrics
          .slice(1)
          .filter((key) => shows(key))
          .map((key) => series.find((s) => s.key === key))
          .filter((s): s is MetricSeries => s !== undefined)
          .slice(0, MAX_SUPPORTING),
      );
    }
  }

  const measured = backing.kind === "metric";
  const note = backing.note ?? NO_VALUE_YET;
  const { strengths, improvements, total } = mentionsFor(selected, goal.key);
  if (total === 0 || (strengths === 0 && improvements === 0)) {
    return measured
      ? { kind: "no-value", note }
      : { kind: "mentions", strengths, improvements, total, latest: null, note, measured };
  }

  return {
    kind: "mentions",
    strengths,
    improvements,
    total,
    // Newest training first, so the first is the most recent.
    latest: statementsFor(selected, [goal.key])[0] ?? null,
    note,
    measured,
  };
}

/** The counting stays in `goalMentions`; this resolves the titles. */
export function recurringOutline(
  sessions: SessionSummary[],
  catalogue: FocusGoal[],
): RecurringOutline {
  const titles = new Map(catalogue.map((goal) => [goal.key, goal.title]));
  const summary = mentionSummary(sessions);
  const resolve = (entries: { goal: string; count: number }[]): RecurringEntry[] =>
    entries.map((entry) => ({
      goal: entry.goal,
      title: titles.get(entry.goal) ?? null,
      count: entry.count,
    }));

  return {
    strengths: resolve(summary.strengths),
    improvements: resolve(summary.improvements),
    total: summary.total,
  };
}
