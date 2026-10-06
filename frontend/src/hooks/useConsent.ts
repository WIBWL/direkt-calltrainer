import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";
import { forgetStoredSessions } from "../sessions";
import type { ConsentState } from "../protocol";

export type ConsentLoadState = "loading" | "ready" | "failed";

/** Held once near the root (ADR 0066). A failed load is not "no consent": the backend fails closed. */
export function useConsent() {
  const [consent, setConsent] = useState<ConsentState | null>(null);
  const [state, setState] = useState<ConsentLoadState>("loading");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await apiFetch<ConsentState>("/api/consent");
        if (!cancelled) {
          setConsent(data);
          setState("ready");
        }
      } catch (e) {
        if (cancelled) return;
        console.debug("[consent] load failed", e);
        setState("failed");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Returns how many trainings a withdrawal removed. */
  const decide = useCallback(async (granted: boolean): Promise<number> => {
    setSaving(true);
    try {
      const data = await apiFetch<ConsentState & { deleted_sessions: number }>(
        "/api/consent",
        { method: "POST", body: JSON.stringify({ granted }) },
      );
      if (!granted) forgetStoredSessions();
      setConsent(data);
      setState("ready");
      return data.deleted_sessions;
    } finally {
      setSaving(false);
    }
  }, []);

  return { consent, state, saving, decide };
}
