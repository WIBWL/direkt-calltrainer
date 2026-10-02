import type {
  FeedbackPoint,
  FocusGoal,
  Measurement,
  MetricAspect,
  SessionFeedback,
  SessionTurn,
} from "../protocol";
import { ASPECT_LABELS, ASPECT_LEADS, METRIC_ASPECTS, metricAspect, withDerived } from "./metrics";

/** What the feedback report says, before layout (F-64, ADR 0102): decided here so
 * `FeedbackView`/`FeedbackScreen` and `feedbackPdf` only draw it and cannot drift.
 * Pure and derived on every render; without consent (ADR 0066) it is the meta
 * line alone. */

/** One wrap-up point, with what it cites already looked up. */
export interface OutlinePoint {
  text: string;
  /** Where in the call the cited utterance starts, or null for a point that
   *  cites none, or one whose Turn is not in the stored transcript. */
  offsetMs: number | null;
  /** The display name of the focus goal it was filed under (ADR 0080), or null
   *  for an untagged point and for a key the catalogue does not know — a goal
   *  retired since (ADR 0076 deactivates rather than deletes). A slug like
   *  `active_listening` in its place would be worse than no tag at all. */
  goal: string | null;
}

/** Which training this was. It describes the *call*, not the wrap-up, so it is
 *  there for a Session whose wrap-up never got written as well. */
export interface CallMeta {
  scenario: string | null;
  partner: string;
  /** Which side the User was on, for a reverse only (ADR 0070): the transcript
   *  reads very differently depending on it. Null for an ordinary call. */
  reversal: string | null;
}

export interface WrapUpOutline {
  summary: string;
  strengths: OutlinePoint[];
  improvements: OutlinePoint[];
  phaseLanguage: string | null;
}

/** One of the two halves the metrics are read in (ADR 0082). Both are always
 *  present, an empty one included: the page decides from that whether there
 *  is anything to switch between. */
export interface MetricGroup {
  aspect: MetricAspect;
  label: string;
  lead: string;
  measurements: Measurement[];
}

export interface ReportOutline {
  meta: CallMeta;
  /** Null without a wrap-up: no consent, or one that failed or is still on its
   *  way. The report is then the protocol, and says so. */
  wrapUp: WrapUpOutline | null;
  metricGroups: MetricGroup[];
}

export interface ReportInput {
  personaName: string;
  scenarioName?: string | null | undefined;
  reverse?: boolean | undefined;
  feedback?: SessionFeedback | null | undefined;
  measurements?: Measurement[] | undefined;
  /** The stored utterances, which a point's `turn_id` refers to. */
  turns?: SessionTurn[] | undefined;
  /** The focus-goal catalogue, for naming a point's tag. Empty while it has not
   *  loaded, and the tags are then simply absent. */
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
