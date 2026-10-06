import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";
import type { FocusChoice, FocusState } from "../protocol";

export type FocusLoadState = "loading" | "ready" | "failed";

/** Held once near the root (F-62, ADR 0076). A failed load is not "undecided", or it would re-ask. */
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

  /** No goals is "no focus", a real answer. */
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
