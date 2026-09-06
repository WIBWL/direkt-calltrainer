import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "../api";
import type { SessionDetail } from "../protocol";

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
 * The backend writes the Session before it sends session.ended, so a 404 here
 * is conclusive — the write failed — rather than the client being early.
 *
 * Goes through apiFetch: the route needs the same bearer token as the rest of
 * /api (ADR 0009).
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
        const data = await apiFetch<SessionDetail>(`/api/sessions/${sessionId}`);
        if (cancelled) return;
        errors = 0;
        setDetail(data);
        if (data.feedback) return setState("ready");
        if (data.status === "failed") return setState("failed");
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) return setState("missing");
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
