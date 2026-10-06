import { useCallback, useEffect, useState } from "react";

import type { SessionSummary } from "../protocol";
import { listSessions } from "../sessions";

/** Larger than a step, so only every other press waits on the network. */
const PAGE_SIZE = 20;

const FIRST_ROWS = 3;
const STEP_ROWS = 10;

export type HistoryState = "loading" | "ready" | "failed";

/** F-48, one page at a time (ADR 0064). */
export function useSessionHistory() {
  const [loaded, setLoaded] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<HistoryState>("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  const [shown, setShown] = useState(FIRST_ROWS);

  const [requestedPages, setRequestedPages] = useState(1);

  useEffect(() => {
    let cancelled = false;
    const offset = (requestedPages - 1) * PAGE_SIZE;
    if (offset > 0) setLoadingMore(true);

    void (async () => {
      try {
        const page = await listSessions(PAGE_SIZE, offset);
        if (cancelled) return;
        setTotal(page.total);
        // De-duplicated: a Session written between pages shifts every row by one.
        setLoaded((previous) => {
          const merged = offset === 0 ? page.sessions : [...previous, ...page.sessions];
          const seen = new Set<string>();
          return merged.filter((s) => !seen.has(s.session_id) && seen.add(s.session_id));
        });
        setState("ready");
      } catch (e) {
        if (cancelled) return;
        console.debug("[history] load failed", e);
        setState("failed");
      } finally {
        if (!cancelled) setLoadingMore(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [requestedPages]);

  // One action, not an effect on `shown`, so a press never starts a second request.
  const showMore = useCallback(() => {
    const next = shown < STEP_ROWS ? STEP_ROWS : shown + STEP_ROWS;
    setShown(next);
    if (next > loaded.length && loaded.length < total) setRequestedPages((n) => n + 1);
  }, [shown, loaded.length, total]);

  // Local, not a refetch: re-reading the offsets would skip a row.
  const removeSession = useCallback((sessionId: string) => {
    setLoaded((previous) => previous.filter((s) => s.session_id !== sessionId));
    setTotal((previous) => Math.max(0, previous - 1));
  }, []);

  return {
    sessions: loaded.slice(0, shown),
    total,
    state,
    loadingMore,
    /** Loaded or not. */
    hasMore: shown < total,
    showMore,
    removeSession,
  };
}
