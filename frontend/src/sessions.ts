import { ApiError, apiFetch } from "./api";
import type { SessionDetail, SessionHistoryPage } from "./protocol";

/**
 * Routes for reading and removing the caller's own stored Sessions; React state
 * stays in the screens (polling and reading once differ, ADR 0019).
 * `createReverse`/`createFollowUp` return a Scenario, so live in `scenarioLibrary.ts`.
 */

/**
 * The most rows one request may ask for (ADR 0064); asking for more silently
 * gets this many back. Callers may ask for fewer.
 */
export const MAX_PAGE_SIZE = 100;

/**
 * One stored Session, or null for "no such Session" and "not yours" alike — the
 * route answers 404 to both (ADR 0031/0050). Anything else throws, so a poller
 * can tell "never arriving" from "that attempt failed".
 */
export async function getSession(sessionId: string): Promise<SessionDetail | null> {
  try {
    return await apiFetch<SessionDetail>(`/api/sessions/${sessionId}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/**
 * The last few settled Sessions read, so a step from a training to one of its
 * Kennzahlen and back does not fetch the same detail, curves and all, three
 * times. Only a finished or failed wrap-up is kept: one still being written
 * would stay "being written" on every later visit.
 */
const settled = new Map<string, SessionDetail>();
const SETTLED_KEPT = 5;

/** `getSession` through that cache. `fresh` skips it, for a re-read after the
 *  Session changed (a follow-up written, a retry accepted). */
export async function readStoredSession(
  sessionId: string,
  fresh = false,
): Promise<SessionDetail | null> {
  const kept = fresh ? undefined : settled.get(sessionId);
  if (kept) return kept;
  const data = await getSession(sessionId);
  settled.delete(sessionId);
  if (data && (data.status === "done" || data.status === "failed")) {
    settled.set(sessionId, data);
    if (settled.size > SETTLED_KEPT) settled.delete(settled.keys().next().value!);
  }
  return data;
}

/** Drop every kept Session, after a withdrawal of consent deleted them all. */
export const forgetStoredSessions = () => settled.clear();

/**
 * One page of the caller's own finished Sessions, newest first (F-48). The route
 * filters by the caller's subject (ADR 0064).
 */
export const listSessions = (limit: number, offset: number) =>
  apiFetch<SessionHistoryPage>(`/api/sessions?limit=${limit}&offset=${offset}`);

/**
 * Ask for a failed wrap-up to be written again from the stored Transcript and
 * Measurements (ADR 0049). 202 → go back to polling. 409 = nothing to retry
 * (exists, empty call, or job still running); 503 = queue unreachable, try later.
 */
export const retryFeedback = (sessionId: string) =>
  apiFetch(`/api/sessions/${sessionId}/feedback`, { method: "POST" });

/** Delete one stored training. 404s for an id that is absent *or* not the
 * caller's, exactly as the read does. */
export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  settled.delete(sessionId);
}
