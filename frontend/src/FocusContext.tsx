import { createContext, useContext, type ReactNode } from "react";

import FocusDialog from "./components/FocusDialog";
import { useFocus } from "./hooks/useFocus";
import type { FocusChoice, FocusState } from "./protocol";

interface FocusContextValue {
  focus: FocusState | null;
  saving: boolean;
  choose: (choice: FocusChoice) => Promise<FocusState>;
}

const FocusContext = createContext<FocusContextValue | null>(null);

/**
 * Holds the training focus app-wide, one fetch, asked once (F-62, ADR 0076).
 * Inside the consent gate so the legally required question comes first. Never
 * blocks on a *failed* load: a focus changes emphasis, not whether the app works.
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
