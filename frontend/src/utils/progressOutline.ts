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

/** What the progress report says before anybody lays it out (F-13): the
 * counterpart of `reportOutline.ts` for the second document this application
 * writes (ADR 0102). Pure, derived on every render, stored nowhere. It decides
 * what is *claimed* and never how a reading looks, which is the half that must
 * not differ between the screen and the sheet somebody hands on. Left to
 * themselves the two had drifted: the file named a measured goal whose selection
 * holds no value while the screen drew an empty box, and `progressPdf` carried
 * its own copy of the mention arithmetic. */

/** How a focus goal is answered, and with what. One variant per shape a tile
 *  and a paragraph both have to take. */
export type FocusReading =
  /** A measured goal with a figure in this selection. */
  | {
      kind: "metric";
      series: MetricSeries;
      /** The most recent value, already formatted. Null for a series with no
       *  points, which `kind: "no-value"` covers instead. */
      last: string | null;
      /** The user's own usual range in words, or null below the series
       *  threshold. Never a target (ADR 0051). */
      band: string | null;
      /** How many of the readable trainings carry this figure. */
      trainings: number;
      /** How many readable trainings carry no value for it. Two reasons and the
       *  interface claims neither: a metric younger than the call (ADR 0048), or
       *  a recording too noisy to split speech from silence (ADR 0085). */
      missing: number;
      /** The goal's further figures, most telling first, already filtered to
       *  the ones a cross-call view may show. */
      supporting: MetricSeries[];
    }
  /** Measured, but nothing in this selection carries it. The case that used to
   *  fall through to an empty tile. */
  | { kind: "no-value"; note: string }
  /** Answered by a comparison of two stretches of one call, never a series
   *  (ADR 0081). */
  | { kind: "segment"; trainings: number }
  /** Answered by the activity block at the top of the screen. */
  | { kind: "activity"; goal: string }
  /** Answered by what the wrap-ups wrote. `measured` tells the two ways in
   *  apart: a goal that has no measurement at all, and one that has one which
   *  this selection does not carry. Only the first may say "keine Messung". */
  | {
      kind: "mentions";
      strengths: number;
      improvements: number;
      total: number;
      /** The newest thing a wrap-up wrote about it, or null. */
      latest: GoalStatement | null;
      /** What to say where the wrap-ups have said nothing yet. */
      note: string;
      measured: boolean;
    };

export interface FocusOutline {
  key: string;
  title: string;
  reading: FocusReading;
}

/** One theme the wrap-ups kept naming, with its title already looked up. */
export interface RecurringEntry {
  goal: string;
  /** The catalogue title, or null for a goal retired since (ADR 0076
   *  deactivates rather than deletes). The raw key is a poor label but an
   *  honest one, and nothing may link to a page that can only say the name is
   *  unknown. */
  title: string | null;
  count: number;
}

export interface RecurringOutline {
  strengths: RecurringEntry[];
  improvements: RecurringEntry[];
  /** Trainings whose wrap-up carried any tag. The denominator, named wherever
   *  a count appears (ADR 0080). */
  total: number;
}

export interface ProgressOutlineInput {
  /** The goals the user picked, resolved against the catalogue and in its
   *  order. */
  goals: FocusGoal[];
  /** Every series of the selection, the call length included. */
  series: MetricSeries[];
  /** The trainings both switches selected. What the mention counts are read
   *  over: a statement is a statement whatever the call's length. */
  selected: SessionSummary[];
  /** Those of them long enough for their figures to be read (`readable`). The
   *  denominator behind "aus N Trainings". */
  readable: SessionSummary[];
  /** Whether a metric earns a row at all — `showsInOverview`, handed in rather
   *  than imported, so this module never has to know why a metric is hidden. */
  shows: (key: string) => boolean;
}

/** How many of a goal's further metrics stand beside the first. Two: `pace` and
 *  `active_listening` name three between them, which together are the goal, and
 *  a third would turn a tile into the table below it. */
const MAX_SUPPORTING = 2;

/** What each picked goal reads, in catalogue order: four shapes because the
 *  honest answer differs per goal, plus a fifth that is an absence rather than a
 *  shape — a measured goal whose selection carries no value
 *  (`focusMetrics.NO_VALUE_YET`). Nothing is dropped for having nothing to say;
 *  a tile that disappears lets the user believe the goal is being tracked. */
export function focusOutline(input: ProgressOutlineInput): FocusOutline[] {
  return input.goals.map((goal) => ({
    key: goal.key,
    title: goal.title,
    reading: readingFor(goal, input),
  }));
}

/** One metric as a reading: last value, own usual range and the trainings each
 *  is out of, already in words. Exported because the overview that stands in
 *  when no goals are picked says the same thing about a metric reached a
 *  different way, and "the same thing" has to mean the same sentences — it used
 *  to render its own, with a count that made the "no value in N trainings" line
 *  unreachable. Not `utils/metrics`' `metricReading`, which reads one call. */
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

  // Either a goal with no measurement, or a measured one this selection does
  // not carry. Both are answered by what the wrap-ups wrote, and both say so
  // differently, which is what `measured` is for.
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
    // `statementsFor` is newest training first and keeps the wrap-up's own
    // order within one, so the first entry is the most recent sentence.
    latest: statementsFor(selected, [goal.key])[0] ?? null,
    note,
    measured,
  };
}

/**
 * What the wrap-ups keep naming, with the catalogue titles resolved.
 *
 * The counting itself stays in `goalMentions` — per training and not per point,
 * over a denominator of the trainings that could have named it. This adds the
 * one thing both renderings need and neither should look up for itself.
 */
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
