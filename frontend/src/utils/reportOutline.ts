import type {
  FeedbackPoint,
  FocusGoal,
  Measurement,
  MetricAspect,
  SessionFeedback,
  SessionTurn,
} from "../protocol";
import { ASPECT_LABELS, ASPECT_LEADS, METRIC_ASPECTS, metricAspect, withDerived } from "./metrics";

/** What the feedback report says, for the page and the PDF alike (F-64, ADR 0102). */

export interface OutlinePoint {
  text: string;
  /** Null if it cites nothing or its Turn is not stored. */
  offsetMs: number | null;
  /** Null untagged or for a retired goal (ADR 0076); a raw slug would be worse. */
  goal: string | null;
}

/** Describes the call, so it exists without a wrap-up too. */
export interface CallMeta {
  scenario: string | null;
  partner: string;
  /** ADR 0070; null for an ordinary call. */
  reversal: string | null;
}

export interface WrapUpOutline {
  summary: string;
  strengths: OutlinePoint[];
  improvements: OutlinePoint[];
  phaseLanguage: string | null;
}

/** ADR 0082. Both always present, so the page can tell whether to switch. */
export interface MetricGroup {
  aspect: MetricAspect;
  label: string;
  lead: string;
  measurements: Measurement[];
}

export interface ReportOutline {
  meta: CallMeta;
  /** Null without a wrap-up: the report is then the protocol. */
  wrapUp: WrapUpOutline | null;
  metricGroups: MetricGroup[];
}

export interface ReportInput {
  personaName: string;
  scenarioName?: string | null | undefined;
  reverse?: boolean | undefined;
  feedback?: SessionFeedback | null | undefined;
  measurements?: Measurement[] | undefined;
  turns?: SessionTurn[] | undefined;
  /** Empty while loading; the tags are then absent. */
  goals?: FocusGoal[] | undefined;
}

export function callMeta(
  personaName: string,
  scenarioName: string | null | undefined,
  reverse: boolean | undefined,
): CallMeta {
  return {
    scenario: scenarioName || null,
    partner: personaName,
    reversal: reverse ? `Sie riefen an, ${personaName} nahm ab` : null,
  };
}

export function wrapUpOutline(
  feedback: SessionFeedback,
  turns: SessionTurn[],
  goals: FocusGoal[],
): WrapUpOutline {
  const resolve = (point: FeedbackPoint): OutlinePoint => ({
    text: point.text,
    offsetMs:
      point.turn_id === null
        ? null
        : (turns.find((turn) => turn.turn_id === point.turn_id)?.start_offset_ms ?? null),
    goal: point.goal ? (goals.find((goal) => goal.key === point.goal)?.title ?? null) : null,
  });
  return {
    summary: feedback.summary,
    strengths: feedback.points.filter((p) => p.kind === "strength").map(resolve),
    improvements: feedback.points.filter((p) => p.kind === "improvement").map(resolve),
    phaseLanguage: feedback.phase_language || null,
  };
}

export function metricGroups(measurements: Measurement[]): MetricGroup[] {
  const all = withDerived(measurements);
  return METRIC_ASPECTS.map((aspect) => ({
    aspect,
    label: ASPECT_LABELS[aspect],
    lead: ASPECT_LEADS[aspect],
    measurements: all.filter((measurement) => metricAspect(measurement) === aspect),
  }));
}

export function reportOutline({
  personaName,
  scenarioName,
  reverse,
  feedback,
  measurements = [],
  turns = [],
  goals = [],
}: ReportInput): ReportOutline {
  return {
    meta: callMeta(personaName, scenarioName, reverse),
    wrapUp: feedback ? wrapUpOutline(feedback, turns, goals) : null,
    metricGroups: metricGroups(measurements),
  };
}
