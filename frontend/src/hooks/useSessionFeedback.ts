import { useEffect, useState } from "react";

import type { SessionDetail } from "../protocol";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const POLL_INTERVAL_MS = 2000;
// Generation is one LLM call and normally lands in a few seconds. Well past
// that, the worker is not coming; say so rather than leave a spinner running.
const POLL_TIMEOUT_MS = 60_000;
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
        const response = await fetch(`${API_URL}/api/sessions/${sessionId}`);
        if (cancelled) return;
        if (response.status === 404) return setState("missing");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data: SessionDetail = await response.json();
        if (cancelled) return;
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
