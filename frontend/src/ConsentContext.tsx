import { createContext, useContext, type ReactNode } from "react";

import ConsentDialog from "./components/ConsentDialog";
import { useConsent } from "./hooks/useConsent";
import type { ConsentState } from "./protocol";

interface ConsentContextValue {
  consent: ConsentState | null;
  saving: boolean;
  decide: (granted: boolean) => Promise<number>;
}

const ConsentContext = createContext<ConsentContextValue | null>(null);

/** One fetch, app-wide (ADR 0066). A failed load never blocks: the backend fails closed by itself. */
export function ConsentProvider({ children }: { children: ReactNode }) {
  const { consent, state, saving, decide } = useConsent();

  if (state === "loading") {
    return <p id="status">Lädt …</p>;
  }

  if (state === "ready" && consent?.decision_required) {
    return <ConsentDialog onDecide={decide} saving={saving} />;
  }

  return (
    <ConsentContext.Provider value={{ consent, saving, decide }}>
      {children}
    </ConsentContext.Provider>
  );
}

/** Null while unknown: a failed load, not a "no". */
export function useConsentContext(): ConsentContextValue {
  const value = useContext(ConsentContext);
  if (value === null) {
    throw new Error("useConsentContext must be used inside <ConsentProvider>");
  }
  return value;
}
