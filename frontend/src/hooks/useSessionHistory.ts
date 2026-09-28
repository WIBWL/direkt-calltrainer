import { useCallback, useEffect, useState } from "react";

import type { SessionSummary } from "../protocol";
import { listSessions } from "../sessions";

/** How many rows one request fetches — the `limit` sent to the server and the
 * stride its `offset` counts in. Not what the screen shows: that is capped
 * below, and deliberately smaller, so that only every other press has to wait
 * on the network. The backend caps a page at 100 (ADR 0064). */
const PAGE_SIZE = 20;

/** Rows shown at first (a glance, on the profile screen) and added per press.
 * Display only: `showMore` fetches the next `PAGE_SIZE` page only when the rows
 * to reveal are missing, and a step is smaller than a page, so a press waits on
 * at most one request. */
const FIRST_ROWS = 3;
const STEP_ROWS = 10;

export type HistoryState = "loading" | "ready" | "failed";

/**
 * The caller's own finished Sessions, newest first (F-48), one page at a time,
 * appended on demand. The route itself scopes to the caller (ADR 0064).
 */
export function useSessionHistory() {
  const [loaded, setLoaded] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<HistoryState>("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  // How many of the loaded rows the screen may show. Separate from how many
  // are held, because a page arrives twice the size of a step.
  const [shown, setShown] = useState(FIRST_ROWS);

  // Bumped to ask for another page; also what a retry re-runs.
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
        // Replace on the first page, append after — and de-duplicate by id,
        // because a Session written between two page requests shifts every
        // later row by one under offset pagination (ADR 0064) and would
        // otherwise show up twice.
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

  // One press: reveal the next step, and fetch the page those rows are on if
  // they are not held yet. Written as one action rather than as an effect
  // watching `shown`, so a press can never set off a second request while the
  // first is still in flight.
  const showMore = useCallback(() => {
    const next = shown < STEP_ROWS ? STEP_ROWS : shown + STEP_ROWS;
    setShown(next);
    if (next > loaded.length && loaded.length < total) setRequestedPages((n) => n + 1);
  }, [shown, loaded.length, total]);

  // Drops a Session the server has already deleted. Local rather than a
  // refetch: re-requesting the same offsets after a row disappeared would pull
  // rows across page boundaries and skip one.
  const removeSession = useCallback((sessionId: string) => {
    setLoaded((previous) => previous.filter((s) => s.session_id !== sessionId));
    setTotal((previous) => Math.max(0, previous - 1));
  }, []);

  return {
    /** What the screen renders: the loaded rows, capped at what has been
     * revealed. Shorter than the cap once the end of the history is reached. */
    sessions: loaded.slice(0, shown),
    total,
    state,
    loadingMore,
    /** True while rows exist that are not being shown -- whether or not they
     * are already loaded. */
    hasMore: shown < total,
    showMore,
    removeSession,
  };
}
