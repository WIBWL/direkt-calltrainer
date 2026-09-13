import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";
import type { FocusChoice, FocusState } from "../protocol";

export type FocusLoadState = "loading" | "ready" | "failed";

/**
 * The signed-in user's training focus and the catalogue it comes from
 * (F-62, ADR 0076).
 *
 * Held once, near the root, and passed down: the first-run dialog and the
 * profile section show the same catalogue and the same ticks, and fetching it
 * twice would let the two disagree on screen after one of them has just saved.
 *
 * A failed load is deliberately not treated as "undecided". Blocking the app
 * with a dialog because a request timed out would ask a user who answered
 * months ago to answer again, and the answer they give under that dialog would
 * overwrite the one they already had.
 */
export function useFocus() {
  const [focus, setFocus] = useState<FocusState | null>(null);
  const [state, setState] = useState<FocusLoadState>("loading");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await apiFetch<FocusState>("/api/focus");
        if (!cancelled) {
          setFocus(data);
          setState("ready");
        }
      } catch (e) {
        if (cancelled) return;
        console.debug("[focus] load failed", e);
        setState("failed");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Replace the selection. No goals is "no focus" — a real answer. */
  const choose = useCallback(async (choice: FocusChoice): Promise<FocusState> => {
    setSaving(true);
    try {
      const data = await apiFetch<FocusState>("/api/focus", {
        method: "PUT",
        body: JSON.stringify(choice),
      });
      setFocus(data);
      setState("ready");
      return data;
    } finally {
      setSaving(false);
    }
  }, []);

  return { focus, state, saving, choose };
}
