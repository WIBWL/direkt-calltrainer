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
// How much longer to keep polling after the wrap-up has landed, for the
// follow-up Scenario written from it (ADR 0069). One further model call, and
// one that is allowed to produce nothing at all — so it gets a deadline of its
// own rather than the full one above, which would leave the screen saying
// "wird erstellt" for ten minutes about something that never started.
const FOLLOW_UP_GRACE_MS = 180_000;

/** "missing" means the Session itself was never stored, which is a different
 * failure from a wrap-up that could not be generated. "loading" outlives the
 * wrap-up: it also covers the follow-up Scenario drafted from it. */
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
/** Whether a follow-up is still to be expected: one is written only where the
 * wrap-up names something to work on (ADR 0069). */
const awaitsFollowUp = (detail: SessionDetail) =>
  detail.feedback?.points.some((point) => point.kind === "improvement") ?? false;

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
    let deadline = Date.now() + POLL_TIMEOUT_MS;
    setState("loading");
    setDetail(null);

    const poll = async () => {
      try {
        const data = await apiFetch<SessionDetail>(`/api/sessions/${sessionId}`);
        if (cancelled) return;
        errors = 0;
        setDetail(data);
        if (data.feedback) {
          // The follow-up is written after the wrap-up, so keep the one poller
          // running through the gap rather than starting a second one. Nothing
          // is waiting on it: the report is already on screen either way.
          if (data.follow_up || !awaitsFollowUp(data)) return setState("ready");
          deadline = Math.min(deadline, Date.now() + FOLLOW_UP_GRACE_MS);
        }
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
