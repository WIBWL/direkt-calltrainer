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

/** A poll's answer, labelled with the Session it is an answer about. */
interface Result {
  sessionId: string | null;
  detail: SessionDetail | null;
  state: FeedbackState;
}

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
  const [result, setResult] = useState<Result>(() => ({
    sessionId,
    detail: null,
    state: sessionId === null ? "missing" : "loading",
  }));

  useEffect(() => {
    if (sessionId === null) return undefined;

    let cancelled = false;
    let timer: number | undefined;
    let errors = 0;
    let latest: SessionDetail | null = null;
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    const settle = (state: FeedbackState) => setResult({ sessionId, detail: latest, state });

    const poll = async () => {
      try {
        const data = await getSession(sessionId);
        if (cancelled) return;
        // Conclusive, so stop polling: the backend writes the Session before it
        // sends session.ended, and the route answers the same for absent and
        // not-yours (ADR 0031/0050).
        if (data === null) return settle("missing");
        errors = 0;
        latest = data;
        if (data.feedback) return settle("ready");
        if (data.status === "failed") return settle("failed");
        settle("loading");
      } catch (e) {
        if (cancelled) return;
        console.debug("[feedback] poll failed", e);
        if (++errors >= MAX_CONSECUTIVE_ERRORS) return settle("failed");
      }
      if (Date.now() >= deadline) return settle("failed");
      timer = window.setTimeout(poll, POLL_INTERVAL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sessionId]);

  // The render that hands in a new id comes *before* the effect that starts
  // polling it, and a screen mounted in that same render runs its own effects
  // first. So an answer about the previous id — during a call the id is null,
  // which reads "missing" — must never be passed off as one about this id: the
  // waiting screen took exactly that for a settled wrap-up and moved on before
  // it was ever seen. Derived here rather than reset in the effect, which would
  // be one render too late.
  if (result.sessionId !== sessionId) {
    return sessionId === null
      ? { detail: null, state: "missing" as const }
      : { detail: null, state: "loading" as const };
  }
  return { detail: result.detail, state: result.state };
}
