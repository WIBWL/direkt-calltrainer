import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "../api";
import type { SessionDetail } from "../protocol";

/** "missing" is a 404 — no such Session, or not the caller's (ADR 0031/0050),
 *  which are deliberately the same answer. */
export type StoredSessionState = "loading" | "ready" | "missing" | "failed";

/**
 * One stored Session, read once.
 *
 * The counterpart to `useSessionFeedback`, and the difference is the whole
 * point: that hook polls, because it runs the moment a call ends, when the
 * wrap-up genuinely is still being generated (ADR 0019). Opened from the
 * history days later, nothing is in flight — whatever the database holds is
 * the final answer, and polling for it would only spend a minute implying that
 * something is on its way.
 *
 * A Session without a wrap-up is therefore `ready` here, not an error: the
 * Transcript and the figures are still there, and the caller says plainly that
 * the narrative is not.
 */
export function useStoredSession(sessionId: string | null) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [state, setState] = useState<StoredSessionState>("loading");

  useEffect(() => {
    if (sessionId === null) {
      setState("missing");
      return;
    }

    let cancelled = false;
    setState("loading");
    setDetail(null);

    void (async () => {
      try {
        const data = await apiFetch<SessionDetail>(`/api/sessions/${sessionId}`);
        if (cancelled) return;
        setDetail(data);
        setState("ready");
      } catch (e) {
        if (cancelled) return;
        console.debug("[stored session] load failed", e);
        setState(e instanceof ApiError && e.status === 404 ? "missing" : "failed");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return { detail, state };
}
