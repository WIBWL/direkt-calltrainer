import { useCallback, useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";
import { getSession } from "../sessions";

const POLL_INTERVAL_MS = 2000;
// Must not be shorter than the backend's JOB_TIMEOUT_S (backend/feedback/
// queue.py), or this screen reports a failure on work still running.
// Generation runs in thinking mode and may be retried once.
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
 * Polls the finished Session until its wrap-up settles (generated async, ADR 0019).
 * The Session is written before session.ended, so an absent one (`getSession`
 * null) means the write failed, not that the client is early.
 */
export function useSessionFeedback(sessionId: string | null) {
  const [result, setResult] = useState<Result>(() => ({
    sessionId,
    detail: null,
    state: sessionId === null ? "missing" : "loading",
  }));

  // Bumped to poll again for the same Session. The effect keys on it, which
  // is what lets a wrap-up asked for a second time be waited for at all: the
  // first poll has long since settled on `failed` and its deadline is spent.
  const [attempt, setAttempt] = useState(0);

  const restart = useCallback(() => {
    if (sessionId === null) return;
    // Straight to "loading", rather than waiting for the first answer: the
    // press has to change something on screen at once, or it reads as a button
    // that did nothing.
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
  }, [sessionId, attempt]);

  // A new id arrives a render before the effect that polls it, and a screen
  // mounted in that render reads first: an answer about the previous id (null
  // during a call, which reads "missing") must not pass as one about this id.
  // Derived here because resetting in the effect is one render too late.
  if (result.sessionId !== sessionId) {
    return sessionId === null
      ? { detail: null, state: "missing" as const, restart }
      : { detail: null, state: "loading" as const, restart };
  }
  return { detail: result.detail, state: result.state, restart };
}
