/**
 * The app's URLs, in one place: a typo in the route table, a link or the
 * post-login return is a silent redirect to the fallback, not an error.
 */
export const ROUTES = {
  /** The training flow (setup → mic check → call → wrap-up). */
  training: "/",
  /** Account, privacy notice, deletion path and the history (F-31, F-49, F-48). */
  profile: "/profil",
  /** The progress dashboard (F-13, docs/dashboard-concept.md). */
  progress: "/fortschritt",
  /** One metric over time, the dashboard's second level. A route rather than
   *  a panel, so the view can be linked and Back is the browser's. */
  progressMetric: "/fortschritt/:metricKey",
  /** One focus goal over time, the same level for the other half of the
   *  overview. Two segments, so it cannot collide with the metric above even
   *  if a metric key ever reads like a word. */
  progressGoal: "/fortschritt/ziel/:goalKey",
  /** One past training, by the id the listing hands out (ADR 0050). */
  session: "/trainings/:sessionId",
  /** One metric of one training, in detail (F-51's interruptions today). A
   *  page of its own rather than a panel: the transcript excerpts are long,
   *  and a reader should be able to link to them and use Back. */
  sessionMetric: "/trainings/:sessionId/kennzahl/:metricKey",

  // The legal pages the footer links. Their paths are the ones the footer
  // already used, so old links and bookmarks keep working.
  imprint: "/impressum",
  privacy: "/datenschutz",
  accessibility: "/barrierefreiheit",
  /** What the trainer is and is not: an AI, not a person, not an assessment. */
  notes: "/hinweise",
} as const;

/**
 * Handed via location state when a follow-up (F-60) or reverse (F-61) is started
 * from a past training. Not a query parameter, which would survive a reload and
 * start the call again; the training screen consumes it once and clears it.
 */
export interface TrainingStart {
  scenarioId: string;
  personaId: string;
  /** Whether the Scenario is a reverse (ADR 0070), which decides whether the
   * briefing panel is shown. Carried rather than looked up: the row was just
   * written and is not in the training screen's library copy yet. Absent means
   * an ordinary Scenario. */
  reverse?: boolean;
}

/**
 * The URL of one past training. Encoded although the id is a server UUID: it
 * comes over the wire, and an unexpected one must stay one path segment.
 */
export function sessionPath(sessionId: string): string {
  return `/trainings/${encodeURIComponent(sessionId)}`;
}

/** The detail view of one metric. Encoded for the same reason as above,
 *  although a metric key is a slug the backend defines. */
export function progressMetricPath(metricKey: string): string {
  return `/fortschritt/${encodeURIComponent(metricKey)}`;
}

/** The detail view of one focus goal. */
export function progressGoalPath(goalKey: string): string {
  return `/fortschritt/ziel/${encodeURIComponent(goalKey)}`;
}

/** One metric of one training. Both segments encoded, for the reason
 *  `sessionPath` gives. */
export function sessionMetricPath(sessionId: string, metricKey: string): string {
  return `/trainings/${encodeURIComponent(sessionId)}/kennzahl/${encodeURIComponent(metricKey)}`;
}
