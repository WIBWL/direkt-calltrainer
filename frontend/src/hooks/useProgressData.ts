import { useEffect, useState } from "react";

import type { SessionSummary } from "../protocol";
import { MAX_PAGE_SIZE, listSessions } from "../sessions";

/**
 * How many pages the dashboard reads before it stops and says so.
 *
 * It used to read exactly one, and the three counted figures at the top of the
 * screen then described that page while reading as absolutes: "37 Trainings,
 * 12.03. bis 20.09." is a statement about an account, not about a page, and the
 * calendar could not page back past the oldest row it happened to hold. Ten
 * pages is 1000 trainings, which the six-month retention (ADR 0067) puts far
 * out of reach of anything the pilot produces — so in practice the dashboard
 * now reads everything there is, and `truncated` is the honest answer for the
 * account that would nevertheless pass it.
 */
const MAX_PAGES = 10;

export type ProgressLoadState = "loading" | "ready" | "failed";

/**
 * The stored trainings the dashboard is drawn from (F-13).
 *
 * Reads the history endpoint rather than an aggregate of its own: every figure
 * shown on the dashboard was measured when the call ended and stored with the
 * Session (ADR 0051), and `GET /api/sessions` already carries the Measurements
 * per row. An aggregate endpoint would be a second path to the same numbers,
 * and the first thing that would drift.
 *
 * Called by `ProgressProvider` and by nothing else: the three dashboard screens
 * share one load, so walking from a tile into its detail and back does not ask
 * for the whole history again.
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
