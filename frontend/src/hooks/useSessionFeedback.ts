import { useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";
import { getSession } from "../sessions";

const POLL_INTERVAL_MS = 2000;
// Must not be shorter than the backend's JOB_TIMEOUT_S (backend/feedback/
// queue.py): giving up earlier reports a failure on work that is still running,
// and with no listing endpoint that wrap-up is then gone for good. Generation
// is asked in thinking mode and may be retried once, so "a few seconds" no
// longer bounds it. Only this block waits, the transcript renders either way.
const POLL_TIMEOUT_MS = 600_000;
// A request that keeps failing outright is a broken backend, not a slow one.
const MAX_CONSECUTIVE_ERRORS = 3;

/** "missing" means the Session itself was never stored, which is a different
 * failure from a wrap-up that could not be generated. */
export type FeedbackState = "loading" | "ready" | "failed" | "missing";

/**
 * Polls the finished Session until its Feedback settles (ADR 0019 generates it
 * asynchronously, so it does not exist yet when the call ends).
 *
 * The backend writes the Session before it sends session.ended, so an absent
 * Session here is conclusive — the write failed — rather than the client being
 * early. Reading it goes through `sessions.getSession`, which is where that
 * answer is turned into a null.
 *
 * The wrap-up is the only thing it waits for: the follow-up Scenario is asked
 * for by the User and answered by its own request (ADR 0069's amendment).
 */
export function useSessionFeedback(sessionId: string | null) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [state, setState] = useState<FeedbackState>("loading");

  useEffect(() => {
    if (sessionId === null) {
      setState("missing");
      return;
    }

    let cancelled = false;
    let timer: number | undefined;
    let errors = 0;
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    setState("loading");
    setDetail(null);

    const poll = async () => {
      try {
        const data = await getSession(sessionId);
        if (cancelled) return;
        // Conclusive, so stop polling: the backend writes the Session before it
        // sends session.ended, and the route answers the same for absent and
        // not-yours (ADR 0031/0050).
        if (data === null) return setState("missing");
        errors = 0;
        setDetail(data);
        if (data.feedback) return setState("ready");
        if (data.status === "failed") return setState("failed");
      } catch (e) {
        if (cancelled) return;
        console.debug("[feedback] poll failed", e);
        if (++errors >= MAX_CONSECUTIVE_ERRORS) return setState("failed");
      }
      if (Date.now() >= deadline) return setState("failed");
      timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sessionId]);

  return { detail, state };
}
