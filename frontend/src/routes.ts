/**
 * The app's URLs, in one place.
 *
 * Worth a module even at two entries: the path is written in the route table,
 * in every link, and in the post-login return — a typo in any one of them is a
 * silent redirect to the fallback rather than an error, which is exactly the
 * kind of bug that survives review.
 */
export const ROUTES = {
  /** The training flow (setup → mic check → call → wrap-up). */
  training: "/",
  /** Account, privacy notice, deletion path and the history (F-31, F-49, F-48). */
  profile: "/profil",
  /** One past training, by the id the listing hands out (ADR 0050). */
  session: "/trainings/:sessionId",

  // The legal pages the footer links. Their paths are the ones the footer
  // already used, so old links and bookmarks keep working.
  imprint: "/impressum",
  privacy: "/datenschutz",
  accessibility: "/barrierefreiheit",
  /** What the trainer is and is not: an AI, not a person, not an assessment. */
  notes: "/hinweise",
} as const;

/**
 * What the history hands the training flow when a follow-up is started from a
 * past training (F-60), through the router's location state.
 *
 * The two screens are separate routes, so there is no shared component state to
 * put a selection into — and a query parameter would survive a reload and start
 * the call again. The training screen consumes this once and clears it.
 */
export interface TrainingStart {
  scenarioId: string;
  personaId: string;
}

/**
 * The URL of one past training.
 *
 * Encoded even though the id is a UUID the server generated: this value comes
 * back over the wire, and building a URL by concatenation is exactly where an
 * unexpected one stops being a path segment.
 */
export function sessionPath(sessionId: string): string {
  return `/trainings/${encodeURIComponent(sessionId)}`;
}
