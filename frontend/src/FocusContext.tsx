import { createContext, useContext, type ReactNode } from "react";

import FocusDialog from "./components/FocusDialog";
import { useFocus } from "./hooks/useFocus";
import type { FocusState } from "./protocol";

interface FocusContextValue {
  focus: FocusState | null;
  saving: boolean;
  choose: (goals: string[]) => Promise<FocusState>;
}

const FocusContext = createContext<FocusContextValue | null>(null);

/**
 * Holds the training focus for the whole app and asks for it once (F-62,
 * ADR 0076).
 *
 * One fetch, one source of truth — the same arrangement `ConsentProvider` has,
 * and for the same reason: the first-run dialog and the profile section describe
 * the same selection, and two copies of it drift the moment one is saved.
 *
 * Sits *inside* the consent gate, so the two first-run questions are asked in
 * order rather than on top of each other, and the legally required one comes
 * first. Unlike consent, this one is not a gate in any strong sense: "Ohne Fokus
 * fortfahren" is a full answer that costs the user nothing, which is what makes
 * it acceptable to ask before the app appears at all.
 *
 * It never blocks on a *failed* load. A picked focus changes what the app
 * emphasises, not whether it works, so a network blip must not put a dialog in
 * front of someone who answered months ago.
 */
export function FocusProvider({ children }: { children: ReactNode }) {
  const { focus, state, saving, choose } = useFocus();

  if (state === "loading") {
    return <p id="status">Lädt …</p>;
  }

  if (state === "ready" && focus?.decision_required) {
    return <FocusDialog focus={focus} onChoose={choose} saving={saving} />;
  }

  return (
    <FocusContext.Provider value={{ focus, saving, choose }}>
      {children}
    </FocusContext.Provider>
  );
}

/** The current focus. Null while unknown — a failed load, not "no goals". */
export function useFocusContext(): FocusContextValue {
  const value = useContext(FocusContext);
  if (value === null) {
    throw new Error("useFocusContext must be used inside <FocusProvider>");
  }
  return value;
}
