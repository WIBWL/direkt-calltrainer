import { useEffect, useState } from "react";

import { getNextCalls, type NextCallOffer } from "../scenarioLibrary";

/** F-64. Null while there is nothing to ask or the request failed: the block is an extra. */
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
