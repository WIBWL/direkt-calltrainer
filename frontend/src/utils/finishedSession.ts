import type { TranscriptEntry } from "../protocol";

/**
 * The finished Session the post-call screen is showing, kept in
 * `sessionStorage`.
 *
 * Survives a reload but not the tab closing, which is exactly the scope the
 * wrap-up has: it is reachable while this tab is, and is not linkable or
 * listed anywhere. Without it, refreshing the results page — the natural
 * reaction to a wrap-up that is taking a while — silently discarded it.
 */
const STORAGE_KEY = "calltrainer.finishedSession";

export interface FinishedSession {
  sessionId: string | null;
  turns: TranscriptEntry[];
  /** Carried along because a reload restores this screen without a Persona
   * selection to look the name up in. */
  personaName: string;
  /** The Persona that was played, so a reverse started from this screen
   * (ADR 0070) keeps the same voice on the other end of the line. Null after a
   * reload of a Session stored before this field existed. */
  personaId?: string | null;
  /** The Scenario a Zufallsszenario turned out to be (F-62), so the reveal
   * on this screen survives a reload the way `personaName` does. Null or
   * absent for a Scenario the User picked themselves — they know. */
  revealedScenario?: string | null;
}

export function loadFinishedSession(): FinishedSession | null {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as FinishedSession) : null;
  } catch {
    return null; // private mode, cleared storage, or an older shape
  }
}

/** Storage is a convenience here; the current tab works without it, so a
 * failure to write is deliberately swallowed. */
export function saveFinishedSession(finished: FinishedSession | null) {
  try {
    if (finished) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(finished));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // see above
  }
}
