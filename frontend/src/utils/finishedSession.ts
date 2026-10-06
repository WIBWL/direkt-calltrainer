import type { TranscriptEntry } from "../protocol";

/** In `sessionStorage`: a reload (the natural reaction to a slow wrap-up) keeps it, closing the tab does not. */
const STORAGE_KEY = "calltrainer.finishedSession";

export interface FinishedSession {
  sessionId: string | null;
  turns: TranscriptEntry[];
  /** A reload has no selection to look the names up in. */
  personaName: string;
  /** So a reverse started from here keeps the same Persona (ADR 0070). */
  personaId?: string | null;
  scenarioName?: string | null;
}

export function loadFinishedSession(): FinishedSession | null {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as FinishedSession) : null;
  } catch {
    return null; // private mode, cleared storage, or an older shape
  }
}

/** A convenience; a failed write is swallowed. */
export function saveFinishedSession(finished: FinishedSession | null) {
  try {
    if (finished) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(finished));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // see above
  }
}
