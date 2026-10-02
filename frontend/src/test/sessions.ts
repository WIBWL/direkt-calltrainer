import type {
  FeedbackGoalTag,
  SegmentMeasurement,
  SessionSummary,
  SessionSummaryMeasurement,
} from "../protocol";

/**
 * History rows for the dashboard's specs, one builder shared so no spec keeps
 * its own idea of a `SessionSummary`'s shape. Boring defaults (completed, no
 * measurements, no tags), so each fixture reads "the same training, except …".
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
