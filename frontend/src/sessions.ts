import { ApiError, apiFetch } from "./api";
import type { SessionDetail, SessionHistoryPage } from "./protocol";

/** The caller's stored Sessions. `createReverse`/`createFollowUp` live in `scenarioLibrary.ts`. */

/** ADR 0064; more is silently capped. */
export const MAX_PAGE_SIZE = 100;

/** Null for missing and foreign alike (ADR 0031/0050); anything else throws. */
export async function getSession(sessionId: string): Promise<SessionDetail | null> {
  try {
    return await apiFetch<SessionDetail>(`/api/sessions/${sessionId}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** Only settled wrap-ups are kept, or "being written" would stick. */
const settled = new Map<string, SessionDetail>();
const SETTLED_KEPT = 5;

/** `fresh` skips the cache after the Session changed. */
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

/** After a consent withdrawal deleted them all. */
export const forgetStoredSessions = () => settled.clear();

/** F-48, newest first (ADR 0064). */
export const listSessions = (limit: number, offset: number) =>
  apiFetch<SessionHistoryPage>(`/api/sessions?limit=${limit}&offset=${offset}`);

/** ADR 0049. 409 = nothing to retry; 503 = queue unreachable. */
export const retryFeedback = (sessionId: string) =>
  apiFetch(`/api/sessions/${sessionId}/feedback`, { method: "POST" });

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  settled.delete(sessionId);
}
