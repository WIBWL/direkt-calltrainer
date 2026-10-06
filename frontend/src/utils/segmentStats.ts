import type { SegmentMeasurement, SessionSummary } from "../protocol";
import { comparableAcrossCalls } from "./metrics";

/** Demanding stretches against the rest (ADR 0081). Never a difference, ratio or
 * "stability" number: the norm ADR 0051 declines to invent. */

export interface SegmentPair {
  key: string;
  name: string;
  unit: string | null;
  /** Either may be absent where a stretch was too short. */
  pressure: number | null;
  rest: number | null;
}

/** In wire order, stable across reads. */
function pairsOf(segments: SegmentMeasurement[]): SegmentPair[] {
  const byKey = new Map<string, SegmentPair>();
  for (const entry of segments) {
    const pair = byKey.get(entry.key) ?? {
      key: entry.key,
      name: entry.name,
      unit: entry.unit,
      pressure: null,
      rest: null,
    };
    if (entry.segment === "pressure") pair.pressure = entry.value;
    else pair.rest = entry.value;
    byKey.set(entry.key, pair);
  }
  return [...byKey.values()];
}

export function pairFor(
  segments: SegmentMeasurement[],
  metricKey: string,
): SegmentPair | null {
  return pairsOf(segments).find((pair) => pair.key === metricKey) ?? null;
}

export interface SegmentTraining {
  sessionId: string;
  at: string;
  scenario: string;
  persona: string;
  pairs: SegmentPair[];
}

/** Newest first. Loudness is left out across calls, as on the dashboard. */
export function segmentTrainings(sessions: SessionSummary[]): SegmentTraining[] {
  return sessions
    .map((session) => ({
      sessionId: session.session_id,
      at: session.started_at,
      scenario: session.scenario,
      persona: session.persona,
      pairs: pairsOf(session.segments).filter((pair) => comparableAcrossCalls(pair.key)),
    }))
    .filter((training) => training.pairs.length > 0);
}
