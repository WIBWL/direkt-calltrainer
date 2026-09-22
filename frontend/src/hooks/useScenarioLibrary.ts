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

/**
 * The Scenario library as the selection screen holds it: the cards, the two
 * filter rows, which case is picked, and the reload after a row changed.
 *
 * It used to be ten pieces of state, two effects and two memos in `App.tsx`,
 * handed to `SetupView` as a dozen props under names that changed on the way.
 * The rules they follow are pure functions in `scenarioSelection.ts`; this is
 * the state those functions are asked about, and nothing that belongs to the
 * training flow.
 *
 * `preselect` is false while a restored wrap-up owns the screen: nothing is
 * picked or filtered behind it.
 */
export function useScenarioLibrary(preselect: boolean) {
  const [scenarios, setScenarios] = useState<ScenarioCard[]>([]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reloaded after the user creates, edits, shares or deletes a row, so a
  // refetch shows the change without a full page reload. `select` (when passed)
  // is the id to select next — the saved row, or the first remaining one if it
  // was deleted.
  const reload = useCallback(
    (select?: string | null) =>
      listScenarios()
        .then((data) => {
          setScenarios(data);
          if (select !== undefined) setScenarioId(select ?? data[0]?.id ?? null);
        })
        .catch((e) => setError(`Szenarien konnten nicht geladen werden: ${e.message}`)),
    [],
  );

  useEffect(() => {
    listScenarios()
      .then((data) => {
        setScenarios(data);
        if (preselect) {
          setFilters(startingFilters(data));
          setScenarioId(firstSelectable(data));
        }
      })
      .catch((e) => setError(`Szenarien konnten nicht geladen werden: ${e.message}`));
  }, [preselect]);

  const remove = useCallback(
    (id: string) => {
      void deleteScenario(id)
        // Selects whatever is first afterwards, so the screen is never left
        // pointing at a row that is gone.
        .then(() => reload(null))
        .catch((e) => setError(`Szenario konnte nicht entfernt werden: ${e.message}`));
    },
    [reload],
  );

  // Memoised because the effect below depends on them, and a fresh array
  // every render would re-run it every render.
  const visible = useMemo(() => visibleScenarios(scenarios, filters), [scenarios, filters]);
  const pool = useMemo(() => drawPool(scenarios, filters), [scenarios, filters]);
  const counts = useMemo(() => filterCounts(scenarios, filters), [scenarios, filters]);
  const offerRandom = pool.length > 0;

  // The summary must never name a case that is not on the screen above it.
  useEffect(() => {
    setScenarioId((current) => keptSelection(current, visible, offerRandom));
  }, [offerRandom, visible]);

  return {
    scenarios,
    /** The cards the grid shows, in the order it shows them. */
    visible,
    /** What a random Scenario is drawn from; empty means no random tile. */
    pool,
    offerRandom,
    counts,
    filters,
    setFilters,
    /** Whether the suggestions chip is offered at all (F-62). */
    showRecommended: scenarios.some((s) => s.recommendation),
    scenarioId,
    select: setScenarioId,
    selected: scenarios.find((s) => s.id === scenarioId) ?? null,
    reload,
    remove,
    error,
  };
}
