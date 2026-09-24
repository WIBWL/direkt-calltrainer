import { useEffect, useState } from "react";

import type { SessionSummary } from "../protocol";
import { MAX_PAGE_SIZE, listSessions } from "../sessions";

/**
 * How many pages the dashboard reads before it stops and sets `truncated`.
 * The counted figures describe the whole account, so reading one page made
 * them wrong; 1000 trainings is far past what six-month retention (ADR 0067) holds.
 */
const MAX_PAGES = 10;

export type ProgressLoadState = "loading" | "ready" | "failed";

/**
 * The stored trainings the dashboard is drawn from (F-13), read from
 * `GET /api/sessions` rather than an aggregate route that could drift from it.
 * Called only by `ProgressProvider`, so the three dashboard screens share one load.
 */
export function useProgressData() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [complete, setComplete] = useState(true);
  const [state, setState] = useState<ProgressLoadState>("loading");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const loaded: SessionSummary[] = [];
        const seen = new Set<string>();
        let reported = 0;
        let page = 0;

        // Pages are read one after another rather than at once: the later ones
        // exist only on an account nobody has, and a burst of ten requests to
        // find that out would cost every ordinary account a slower first paint.
        for (; page < MAX_PAGES; page += 1) {
          const answer = await listSessions(MAX_PAGE_SIZE, page * MAX_PAGE_SIZE);
          if (cancelled) return;
          reported = answer.total;
          // De-duplicated by id, because a Session written between two requests
          // shifts every later row by one under offset pagination (ADR 0064)
          // and would otherwise arrive twice.
          for (const session of answer.sessions) {
            if (seen.has(session.session_id)) continue;
            seen.add(session.session_id);
            loaded.push(session);
          }
          // An empty or short page is the end of the history. Asking `total`
          // alone would loop forever if a row were deleted mid-read.
          if (answer.sessions.length < MAX_PAGE_SIZE || loaded.length >= reported) break;
        }

        setSessions(loaded);
        setTotal(Math.max(reported, loaded.length));
        setComplete(loaded.length >= reported);
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
    /** True when the account holds more trainings than the cap above reads. */
    truncated: !complete,
    total,
  };
}
