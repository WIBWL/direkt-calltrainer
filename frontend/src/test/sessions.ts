import type {
  FeedbackGoalTag,
  SegmentMeasurement,
  SessionSummary,
  SessionSummaryMeasurement,
} from "../protocol";

/**
 * History rows for the dashboard's specs.
 *
 * One builder shared by the four spec files rather than a literal in each: a
 * `SessionSummary` carries eleven fields, of which any one test cares about
 * two, and spelling out the other nine per case buries what the case is about.
 * The defaults are deliberately the boring ones — a completed training, no
 * measurements, no tags — so every fixture reads as "the same training, except
 * …".
 *
 * Not in the spec files themselves because `progressStats`, `goalMentions` and
 * `segmentStats` all read the same row and would otherwise each keep their own
 * idea of its shape, which is how the `CommittedSession` fixture drifted before
 * the specs were type-checked.
 */

/** Counts up, so two sessions built in a row are never the same row. The id
 *  matters to de-duplication and to the links, never to the arithmetic. */
let next = 0;

export function session(over: Partial<SessionSummary> = {}): SessionSummary {
  next += 1;
  return {
    session_id: `s${next}`,
    persona: "Thomas Brandt",
    scenario: "Störung im Betrieb",
    reverse: false,
    category: "operations",
    status: "completed",
    has_feedback: true,
    feedback_status: "done",
    started_at: "2026-09-01T10:00:00Z",
    ended_at: "2026-09-01T10:05:00Z",
    measurements: [],
    segments: [],
    feedback_goals: [],
    ...over,
  };
}

/** A measured figure as the listing carries it. `active` defaults to true:
 *  a retired metric type is the exception and the specs that care say so. */
export function measurement(
  key: string,
  value: number,
  over: Partial<SessionSummaryMeasurement> = {},
): SessionSummaryMeasurement {
  return {
    key,
    name: key,
    unit: null,
    aspect: "how",
    value,
    active: true,
    ...over,
  };
}

export function tag(
  kind: FeedbackGoalTag["kind"],
  goal: string,
  text = "Ein Satz aus der Auswertung.",
): FeedbackGoalTag {
  return { kind, goal, text };
}

export function segment(
  which: SegmentMeasurement["segment"],
  key: string,
  value: number,
  unit: string | null = null,
): SegmentMeasurement {
  return { segment: which, key, name: key, unit, value };
}
