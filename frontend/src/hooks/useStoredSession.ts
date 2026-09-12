import { useCallback, useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";
import { getSession } from "../sessions";

/** "missing" is what `sessions.getSession` reports as null — no such Session,
 *  or not the caller's (ADR 0031/0050), which are deliberately the same
 *  answer. */
export type StoredSessionState = "loading" | "ready" | "missing" | "failed";

/**
 * One stored Session, read once.
 *
 * The counterpart to `useSessionFeedback`, and the difference is the point:
 * that hook polls because it runs the moment a call ends, when a wrap-up
 * genuinely is being generated (ADR 0019). Opened from the history days later
 * nothing is in flight, and polling would only spend a minute implying
 * otherwise.
 *
 * A Session without a wrap-up is therefore `ready` here, not an error: the
 * Transcript and figures are still there, and the caller says plainly that the
 * narrative is not.
 *
 * `reload` is the one thing that reads it twice: the caller can edit the
 * follow-up this Session produced (F-60), and the card would otherwise keep its
 * pre-edit title.
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
