import { ApiError, apiFetch } from "./api";
import type { SessionDetail, SessionHistoryPage } from "./protocol";

/**
 * Reading and removing the caller's own stored Sessions.
 *
 * The counterpart to `scenarioLibrary.ts`, and the same kind of module: the
 * routes, and what a caller must know to read an answer. The React state
 * machines stay with the screens, because they genuinely differ — the post-call
 * screen polls for a wrap-up that is still being written (ADR 0019), the
 * history reads once, and merging the two as a flag is what ADR 0019's note in
 * CLAUDE.md records as a bug already fixed once.
 *
 * `createReverse` and `createFollowUp` are POSTs under `/api/sessions/` and
 * deliberately live in `scenarioLibrary.ts` instead: both return a Scenario,
 * which is what their callers deal in. A module is named for what it deals in,
 * not for the URL prefix.
 */

/**
 * The most rows one request may ask for (ADR 0064).
 *
 * Here rather than in each caller, which is free to ask for fewer: the history
 * takes a small page because it appends on demand, the dashboard takes the
 * maximum because it draws over the whole set. Asking for more than this
 * silently gets this many back, which is the kind of thing a screen should not
 * have to discover.
 */
export const MAX_PAGE_SIZE = 100;

/**
 * One stored Session, or null when there is none to read.
 *
 * Null covers both "no such Session" and "not yours": the route answers 404 to
 * either, because a 403 would confirm that an id exists (ADR 0031/0050). The
 * distinction does not reach the client and no screen should try to draw one.
 *
 * Anything else — a dead backend, a dropped connection — throws, so a caller
 * that is polling can tell "this will never arrive" from "that attempt
 * failed".
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
 * One page of the caller's own finished Sessions, newest first (F-48).
 *
 * Ownership needs no argument: the route filters by the caller's own subject
 * and offers no way to ask about anyone else (ADR 0064).
 */
export const listSessions = (limit: number, offset: number) =>
  apiFetch<SessionHistoryPage>(`/api/sessions?limit=${limit}&offset=${offset}`);

/** Delete one stored training. 404s for an id that is absent *or* not the
 * caller's, exactly as the read does. */
export const deleteSession = (sessionId: string) =>
  apiFetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
