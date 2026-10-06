import { useCallback, useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";
import { readStoredSession } from "../sessions";

/** "missing": absent or not the caller's, the same answer (ADR 0031/0050). */
export type StoredSessionState = "loading" | "ready" | "missing" | "failed";

/** Read once, never polled (ADR 0019): a missing wrap-up is `ready`, not an error. `reload` bypasses the cache. */
export function useStoredSession(sessionId: string | null) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [state, setState] = useState<StoredSessionState>("loading");
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
        const data = await readStoredSession(sessionId, nonce > 0);
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
