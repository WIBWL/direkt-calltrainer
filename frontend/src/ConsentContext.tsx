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

/**
 * Holds the storage decision app-wide, one fetch, and asks when missing (ADR 0066).
 * Never blocks on a *failed* load: the backend fails closed by itself, so a
 * network blip must not lock out a user who decided long ago.
 */
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

/** The current decision. Null while unknown — a failed load, not a "no". */
export function useConsentContext(): ConsentContextValue {
  const value = useContext(ConsentContext);
  if (value === null) {
    // A component rendered outside the provider would otherwise read "no
    // consent" from a default and quietly tell the user the wrong thing.
    throw new Error("useConsentContext must be used inside <ConsentProvider>");
  }
  return value;
}
