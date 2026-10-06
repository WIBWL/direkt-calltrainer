import { useCallback, useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";
import { getSession } from "../sessions";

const POLL_INTERVAL_MS = 2000;
// At least JOB_TIMEOUT_S (shared/feedback/jobs.py), or running work reads as failed.
const POLL_TIMEOUT_MS = 600_000;
const MAX_CONSECUTIVE_ERRORS = 3;

/** "missing": the Session was never stored, unlike a failed wrap-up. */
export type FeedbackState = "loading" | "ready" | "failed" | "missing";

interface Result {
  sessionId: string | null;
  detail: SessionDetail | null;
  state: FeedbackState;
}

/** Polls until the wrap-up settles (ADR 0019). The Session is written before
 * session.ended, so a null answer means the write failed. */
export function useSessionFeedback(sessionId: string | null) {
  const [result, setResult] = useState<Result>(() => ({
    sessionId,
    detail: null,
    state: sessionId === null ? "missing" : "loading",
  }));

  // Bumped to poll again after a retry.
  const [attempt, setAttempt] = useState(0);

  const restart = useCallback(() => {
    if (sessionId === null) return;
    // At once, or the press seems to do nothing.
    setResult({ sessionId, detail: null, state: "loading" });
    setAttempt((n) => n + 1);
  }, [sessionId]);

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
        // Conclusive (ADR 0031/0050).
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
  }, [sessionId, attempt]);

  // An answer about the previous id must not pass as one about this id; the effect would be a render late.
  if (result.sessionId !== sessionId) {
    return sessionId === null
      ? { detail: null, state: "missing" as const, restart }
      : { detail: null, state: "loading" as const, restart };
  }
  return { detail: result.detail, state: result.state, restart };
}
