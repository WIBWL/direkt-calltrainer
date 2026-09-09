import { useEffect, useState } from "react";

import { apiFetch } from "../api";
import type { SessionHistoryPage, SessionSummary } from "../protocol";

/** The listing caps a page at 100 (ADR 0064). The dashboard asks for one page
 *  and says so when there are more: with the six-month retention (ADR 0067) a
 *  hundred trainings in the window is far beyond anything the pilot produces,
 *  and paging the whole history into a chart would be a second design. */
const MAX_SESSIONS = 100;

export type ProgressLoadState = "loading" | "ready" | "failed";

/**
 * The stored trainings the dashboard is drawn from (F-13).
 *
 * Reads the history endpoint rather than an aggregate of its own: every figure
 * shown on the dashboard was measured when the call ended and stored with the
 * Session (ADR 0051), and `GET /api/sessions` already carries the Measurements
 * per row. An aggregate endpoint would be a second path to the same numbers,
 * and the first thing that would drift.
 */
export function useProgressData() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<ProgressLoadState>("loading");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const page = await apiFetch<SessionHistoryPage>(
          `/api/sessions?limit=${MAX_SESSIONS}&offset=0`,
        );
        if (cancelled) return;
        setSessions(page.sessions);
        setTotal(page.total);
        setState("ready");
      } catch (e) {
        if (cancelled) return;
        console.debug("[progress] load failed", e);
        setState("failed");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    sessions,
    state,
    /** True when the account holds more trainings than one page carries. */
    truncated: total > sessions.length,
    total,
  };
}
