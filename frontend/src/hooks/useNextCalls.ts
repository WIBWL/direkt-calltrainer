import { useEffect, useState } from "react";

import { getNextCalls, type NextCallOffer } from "../scenarioLibrary";

/**
 * The offers for what to play after this call (F-64), fetched once the call is
 * over. Null while there is nothing to ask about or the request failed: the
 * block is an extra, and its absence says nothing wrong happened.
 */
export function useNextCalls(
  scenarioId: string | null,
  personaId: string | null,
  enabled: boolean,
): NextCallOffer[] | null {
  const [offers, setOffers] = useState<NextCallOffer[] | null>(null);

  useEffect(() => {
    setOffers(null);
    if (!enabled || !scenarioId || !personaId) return;
    let cancelled = false;
    getNextCalls(scenarioId, personaId)
      .then((data) => {
        if (!cancelled) setOffers(data);
      })
      .catch((e: unknown) => console.debug("[next calls] failed", e));
    return () => {
      cancelled = true;
    };
  }, [scenarioId, personaId, enabled]);

  return offers;
}
