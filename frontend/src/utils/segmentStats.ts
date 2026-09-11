import type { SegmentMeasurement, SessionSummary } from "../protocol";

/**
 * The demanding stretches of a call against the rest of it (ADR 0081).
 *
 * The data behind F-62's "Souveränität unter Druck", which until now had none:
 * every Kennzahl described a whole call, and a whole call contains both
 * stretches averaged into each other. The wrap-up marks which exchanges were
 * demanding, the backend measures the two stretches separately, and this pairs
 * them up for display.
 *
 * What it does not compute, anywhere: a difference, a ratio, a direction or a
 * verdict. Two figures are put beside each other and the reader draws the
 * comparison. How large a gap means something is exactly the norm ADR 0051
 * declines to invent, and a derived "stability" number would be that norm
 * wearing a different name.
 */

/** One Kennzahl's two figures for one training. */
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
export function pairsOf(segments: SegmentMeasurement[]): SegmentPair[] {
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

/** One training's pair for one Kennzahl, or null where that call has none. */
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

/**
 * The trainings that have a comparison in them, newest first.
 *
 * A training is absent when nobody pushed back in it, when the stretches were
 * too short to measure, and for every call recorded before the per-utterance
 * facts were kept (ADR 0048 — those cannot be recomputed, their audio is
 * gone). All three are the same answer on screen: this call has no comparison,
 * which is not a gap in the data but a fact about the call.
 */
export function segmentTrainings(sessions: SessionSummary[]): SegmentTraining[] {
  return sessions
    .filter((session) => session.segments.length > 0)
    .map((session) => ({
      sessionId: session.session_id,
      at: session.started_at,
      scenario: session.scenario,
      persona: session.persona,
      pairs: pairsOf(session.segments),
    }));
}
