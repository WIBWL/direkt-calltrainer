import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";
import type { FocusChoice, FocusState } from "../protocol";

export type FocusLoadState = "loading" | "ready" | "failed";

/**
 * The signed-in user's training focus and its catalogue (F-62, ADR 0076), held
 * once near the root so dialog and profile agree. A failed load is not
 * "undecided": re-asking would overwrite an answer given months ago.
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
