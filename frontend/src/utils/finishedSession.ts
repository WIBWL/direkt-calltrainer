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
