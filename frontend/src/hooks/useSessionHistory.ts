import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";
import type { SessionHistoryPage, SessionSummary } from "../protocol";

/** One screen of history. The backend caps a page at 100 (ADR 0064). */
const PAGE_SIZE = 20;

export type HistoryState = "loading" | "ready" | "failed";

/**
 * The caller's own finished Sessions, newest first (F-48).
 *
 * Loads one page and appends further ones on demand rather than asking for
 * everything: the endpoint is paginated because a history grows without bound,
 * and a screen that always requested the maximum would quietly stop being
 * complete on the day someone passed it.
 *
 * Ownership needs no argument here — the route filters by the caller's own
 * subject and offers no way to ask about anyone else (ADR 0064).
 */
export function useSessionHistory() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<HistoryState>("loading");
  const [loadingMore, setLoadingMore] = useState(false);

  // Bumped to ask for another page; also what a retry re-runs.
  const [requestedPages, setRequestedPages] = useState(1);

  useEffect(() => {
    let cancelled = false;
    const offset = (requestedPages - 1) * PAGE_SIZE;
    if (offset > 0) setLoadingMore(true);

    void (async () => {
      try {
        const page = await apiFetch<SessionHistoryPage>(
          `/api/sessions?limit=${PAGE_SIZE}&offset=${offset}`,
        );
        if (cancelled) return;
        setTotal(page.total);
        // Replace on the first page, append after — and de-duplicate by id,
        // because a Session written between two page requests shifts every
        // later row by one under offset pagination (ADR 0064) and would
        // otherwise show up twice.
        setSessions((previous) => {
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

  const loadMore = useCallback(() => setRequestedPages((n) => n + 1), []);

  // Drops a Session the server has already deleted. Local rather than a
  // refetch: re-requesting the same offsets after a row disappeared would pull
  // rows across page boundaries and skip one.
  const removeSession = useCallback((sessionId: string) => {
    setSessions((previous) => previous.filter((s) => s.session_id !== sessionId));
    setTotal((previous) => Math.max(0, previous - 1));
  }, []);

  return {
    sessions,
    total,
    state,
    loadingMore,
    /** True while the list is shorter than what the server says exists. */
    hasMore: sessions.length < total,
    loadMore,
    removeSession,
  };
}
