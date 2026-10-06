/** The app's URLs: a typo is a silent redirect to the fallback. */
export const ROUTES = {
  training: "/",
  /** F-31, F-49, F-48. */
  profile: "/profil",
  /** F-13. */
  progress: "/fortschritt",
  progressMetric: "/fortschritt/:metricKey",
  /** Two segments, so it cannot collide with a metric key. */
  progressGoal: "/fortschritt/ziel/:goalKey",
  session: "/trainings/:sessionId",
  sessionMetric: "/trainings/:sessionId/kennzahl/:metricKey",

  // Old paths, kept so links keep working; they forward to the project's pages.
  imprint: "/impressum",
  privacy: "/datenschutz",
  accessibility: "/barrierefreiheit",
  notes: "/hinweise",
} as const;

/** The EFRE DiReKT project's own pages (`ProjectPageLink`). */
export const IMPRINT_URL = "https://efre-direkt.de/imprint/";
export const PRIVACY_URL = "https://efre-direkt.de/privacy/";
export const ACCESSIBILITY_URL = "https://efre-direkt.de/accessibility/";

/** Location state, not a query parameter, which would restart the call on reload. Consumed once. */
export interface TrainingStart {
  scenarioId: string;
  personaId: string;
  /** Carried: the row is not in the library copy yet. */
  reverse?: boolean;
}

/** Encoded: an unexpected id must stay one path segment. */
export function sessionPath(sessionId: string): string {
  return `/trainings/${encodeURIComponent(sessionId)}`;
}

export function progressMetricPath(metricKey: string): string {
  return `/fortschritt/${encodeURIComponent(metricKey)}`;
}

export function progressGoalPath(goalKey: string): string {
  return `/fortschritt/ziel/${encodeURIComponent(goalKey)}`;
}

export function sessionMetricPath(sessionId: string, metricKey: string): string {
  return `/trainings/${encodeURIComponent(sessionId)}/kennzahl/${encodeURIComponent(metricKey)}`;
}
