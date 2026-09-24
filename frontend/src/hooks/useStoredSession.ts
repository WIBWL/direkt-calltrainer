import { useCallback, useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";
import { getSession } from "../sessions";

/** "missing" is what `sessions.getSession` reports as null — no such Session,
 *  or not the caller's (ADR 0031/0050), which are deliberately the same
 *  answer. */
export type StoredSessionState = "loading" | "ready" | "missing" | "failed";

/**
 * One stored Session, read once. Unlike `useSessionFeedback` it never polls
 * (ADR 0019): nothing is in flight days later, so a missing wrap-up is `ready`,
 * not an error. `reload` re-reads after a follow-up was created (F-60).
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
        const data = await getSession(sessionId);
        if (cancelled) return;
        if (data === null) return setState("missing");
        setDetail(data);
        setState("ready");
      } catch (e) {
        if (cancelled) return;
        console.debug("[stored session] load failed", e);
        setState("failed");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId, nonce]);

  return { detail, state, reload };
}
