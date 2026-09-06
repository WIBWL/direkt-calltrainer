import { useCallback, useEffect, useState } from "react";

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
 *
 * `reload` is the one thing that reads it a second time: the caller can edit
 * the follow-up Scenario this Session produced (F-60), and the card shown here
 * would otherwise keep the title it had before that edit.
 */
export function useStoredSession(sessionId: string | null) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [state, setState] = useState<StoredSessionState>("loading");
  // Bumped by `reload`; the effect keys on it, so there is one fetch path and
  // not a second copy of it.
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);

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
  }, [sessionId, nonce]);

  return { detail, state, reload };
}
