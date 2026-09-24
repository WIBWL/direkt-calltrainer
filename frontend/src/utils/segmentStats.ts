import type { SegmentMeasurement, SessionSummary } from "../protocol";
import { comparableAcrossCalls } from "./metrics";

/** A call's demanding stretches against the rest (ADR 0081), for F-62's
 * "composure under pressure". Pairs the backend's two figures for display and
 * never computes a difference, ratio, direction or "stability" number: that
 * would be the norm ADR 0051 declines to invent. */

/** One metric's two figures for one training. */
export interface SegmentPair {
  key: string;
  name: string;
  unit: string | null;
  /** Under pressure, and the rest of the call. Either can be absent: a stretch
   *  too short to measure yields no row, and the other half still says
   *  something on its own. */
  pressure: number | null;
  rest: number | null;
}

/** The pairs of one training, in the order the wire delivered them (metric,
 *  then segment), which is stable across reads. */
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

/** One training's pair for one metric, or null where that call has none. */
export function pairFor(
  segments: SegmentMeasurement[],
  metricKey: string,
): SegmentPair | null {
  return pairsOf(segments).find((pair) => pair.key === metricKey) ?? null;
}

/** One training that carries a comparison, for the goal page's table. */
export interface SegmentTraining {
  sessionId: string;
  /** ISO 8601, the Session's start. */
  at: string;
  scenario: string;
  persona: string;
  pairs: SegmentPair[];
}

/** The trainings with a comparison, newest first (absent: no pressure, stretches
 * too short, or recorded before ADR 0081 — unrecomputable, ADR 0048). Loudness is
 * left out as on the dashboard; the single call keeps it through `pairFor`, where
 * the microphone is the same on both sides. */
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
