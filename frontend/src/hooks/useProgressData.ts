import { useEffect, useState } from "react";

import type { SessionSummary } from "../protocol";
import { MAX_PAGE_SIZE, listSessions } from "../sessions";

/** Far past what six-month retention holds (ADR 0067); beyond it `truncated` is set. */
const MAX_PAGES = 10;

export type ProgressLoadState = "loading" | "ready" | "failed";

/** The dashboard's trainings (F-13), from the history route, loaded once by `ProgressProvider`. */
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

        // One after another: later pages exist only on extreme accounts.
        for (; page < MAX_PAGES; page += 1) {
          const answer = await listSessions(MAX_PAGE_SIZE, page * MAX_PAGE_SIZE);
          if (cancelled) return;
          reported = answer.total;
          // De-duplicated: a Session written mid-read shifts the offsets (ADR 0064).
          for (const session of answer.sessions) {
            if (seen.has(session.session_id)) continue;
            seen.add(session.session_id);
            loaded.push(session);
          }
          // A short page ends it; `total` alone could loop after a deletion.
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
    truncated: !complete,
    total,
  };
}
