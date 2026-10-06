import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteScenario, listScenarios, type ScenarioCard } from "../scenarioLibrary";
import {
  DEFAULT_FILTERS,
  drawPool,
  filterCounts,
  firstSelectable,
  keptSelection,
  startingFilters,
  visibleScenarios,
  type Filters,
} from "../scenarioSelection";

/** The library's cards, filters and pick; the rules are `scenarioSelection.ts`.
 * `preselect` is false while a restored wrap-up owns the screen. */
export function useScenarioLibrary(preselect: boolean) {
  const [scenarios, setScenarios] = useState<ScenarioCard[]>([]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (then: (data: ScenarioCard[]) => void) =>
      listScenarios()
        .then((data) => {
          setScenarios(data);
          then(data);
        })
        .catch((e) => setError(`Szenarien konnten nicht geladen werden: ${e.message}`)),
    [],
  );

  // `select` is the id to pick next, or null for the first remaining.
  const reload = useCallback(
    (select?: string | null) =>
      load((data) => {
        if (select !== undefined) setScenarioId(select ?? data[0]?.id ?? null);
      }),
    [load],
  );

  useEffect(() => {
    void load((data) => {
      if (preselect) {
        setFilters(startingFilters(data));
        setScenarioId(firstSelectable(data));
      }
    });
  }, [load, preselect]);

  const remove = useCallback(
    (id: string) => {
      void deleteScenario(id)
        .then(() => reload(null))
        .catch((e) => setError(`Szenario konnte nicht entfernt werden: ${e.message}`));
    },
    [reload],
  );

  // Memoised: the effect below depends on it.
  const visible = useMemo(() => visibleScenarios(scenarios, filters), [scenarios, filters]);
  const pool = useMemo(() => drawPool(scenarios, filters), [scenarios, filters]);
  const counts = useMemo(() => filterCounts(scenarios, filters), [scenarios, filters]);
  const offerRandom = pool.length > 0;

  useEffect(() => {
    setScenarioId((current) => keptSelection(current, visible, offerRandom));
  }, [offerRandom, visible]);

  return {
    scenarios,
    visible,
    /** Empty means no random tile. */
    pool,
    offerRandom,
    counts,
    filters,
    setFilters,
    showRecommended: scenarios.some((s) => s.recommendation),
    scenarioId,
    select: setScenarioId,
    selected: scenarios.find((s) => s.id === scenarioId) ?? null,
    reload,
    remove,
    error,
  };
}
