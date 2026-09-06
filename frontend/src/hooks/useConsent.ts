import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";
import type { ConsentState } from "../protocol";

export type ConsentLoadState = "loading" | "ready" | "failed";

/**
 * The signed-in user's storage consent (ADR 0066).
 *
 * Held once, near the root, and passed down: the dialog that asks, the notice
 * on the setup screen and the profile's revocation all describe the same fact,
 * and fetching it in three places would let them disagree on screen.
 *
 * A failure to load is deliberately not treated as "no consent". The backend
 * decides what may be stored and fails closed on its own (`consent.py`); a
 * frontend that guessed here would either block a user who has agreed or
 * promise storage to one who has not, and it is not the side that knows.
 */
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

  /** Record a decision. Returns how many stored trainings a withdrawal removed. */
  const decide = useCallback(async (granted: boolean): Promise<number> => {
    setSaving(true);
    try {
      const data = await apiFetch<ConsentState & { deleted_sessions: number }>(
        "/api/consent",
        { method: "POST", body: JSON.stringify({ granted }) },
      );
      setConsent(data);
      setState("ready");
      return data.deleted_sessions;
    } finally {
      setSaving(false);
    }
  }, []);

  return { consent, state, saving, decide };
}
