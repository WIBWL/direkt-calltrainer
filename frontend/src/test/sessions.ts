import type {
  FeedbackGoalTag,
  SegmentMeasurement,
  SessionSummary,
  SessionSummaryMeasurement,
} from "../protocol";

/** The one `SessionSummary` builder for the specs, with boring defaults. */

/** So two built in a row are never the same row. */
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
