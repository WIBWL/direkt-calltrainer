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

/** One fetch, inside the consent gate (F-62, ADR 0076). A failed load never blocks. */
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

/** Null while unknown, not "no goals". */
export function useFocusContext(): FocusContextValue {
  const value = useContext(FocusContext);
  if (value === null) {
    throw new Error("useFocusContext must be used inside <FocusProvider>");
  }
  return value;
}
