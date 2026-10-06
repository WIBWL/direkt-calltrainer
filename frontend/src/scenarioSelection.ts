/** The selection screen's pure functions (ADR 0072). The summary under the grid
 * never names a case that is not on screen. */

import {
  CATEGORY_FILTERS,
  LIBRARY_FILTERS,
  RANDOM_SCENARIO_ID,
  isDrawable,
  matchesCategory,
  matchesFilter,
  type CategoryFilter,
  type LibraryFilter,
  type ScenarioCard,
} from "./scenarioLibrary";

export interface Filters {
  origin: LibraryFilter;
  category: CategoryFilter;
}

/** Everything on both rows: a shortlist hid the User's own Scenarios behind a filter. */
export const DEFAULT_FILTERS: Filters = { origin: "all", category: "all" };

const shows = (card: ScenarioCard, { origin, category }: Filters) =>
  matchesFilter(card, origin) && matchesCategory(card, category);

/** On the suggestions where there are any (F-62), category unfiltered. */
export function startingFilters(scenarios: ScenarioCard[]): Filters {
  return scenarios.some((s) => s.recommendation)
    ? { origin: "recommended", category: "all" }
    : DEFAULT_FILTERS;
}

/** The random tile (F-62), else the first card the starting filters show. */
export function firstSelectable(scenarios: ScenarioCard[]): string | null {
  if (scenarios.some(isDrawable)) return RANDOM_SCENARIO_ID;
  const filters = startingFilters(scenarios);
  return (scenarios.find((s) => shows(s, filters)) ?? scenarios[0])?.id ?? null;
}

/** Sorted by name with an explicit locale, so umlauts sort with their base letter. */
export function visibleScenarios(scenarios: ScenarioCard[], filters: Filters): ScenarioCard[] {
  return scenarios
    .filter((s) => shows(s, filters))
    .sort((a, b) => a.name.localeCompare(b.name, "de"));
}

/** F-62. Empty means no tile: a draw from nothing is a dead button. */
export function drawPool(scenarios: ScenarioCard[], filters: Filters): ScenarioCard[] {
  return scenarios.filter((s) => isDrawable(s) && shows(s, filters));
}

/** Each option counted against the other row's selection (ADR 0072). */
export function filterCounts(
  scenarios: ScenarioCard[],
  filters: Filters,
): { origin: Record<LibraryFilter, number>; category: Record<CategoryFilter, number> } {
  const origin = Object.fromEntries(
    LIBRARY_FILTERS.map((f) => [f, scenarios.filter((s) => shows(s, { ...filters, origin: f })).length]),
  ) as Record<LibraryFilter, number>;
  const category = Object.fromEntries(
    CATEGORY_FILTERS.map((c) => [c, scenarios.filter((s) => shows(s, { ...filters, category: c })).length]),
  ) as Record<CategoryFilter, number>;
  return { origin, category };
}

/** Falls back to the random tile rather than clearing, which left the summary empty. */
export function keptSelection(
  current: string | null,
  visible: ScenarioCard[],
  offerRandom: boolean,
): string | null {
  if (current === RANDOM_SCENARIO_ID) return offerRandom ? current : null;
  if (current !== null && visible.some((card) => card.id === current)) return current;
  return offerRandom ? RANDOM_SCENARIO_ID : null;
}
