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
 * Holds the storage decision for the whole app and asks for it when it is
 * missing (ADR 0060).
 *
 * One fetch, one source of truth. Three screens describe this same fact — the
 * dialog, the setup screen's notice and the profile's revocation — and letting
 * each fetch its own copy is how two of them end up disagreeing on screen after
 * the third has just changed it.
 *
 * The dialog replaces the app rather than floating over a usable one, because
 * an unanswered decision means the next training's fate is undecided. It never
 * blocks on a *failed* load: the backend is what actually enforces storage and
 * fails closed by itself, so a network blip here must not lock a user who has
 * long since decided out of their own trainer.
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
