/**
 * What the selection screen shows and which case is picked: pure functions over
 * the cards and both filter rows (ADR 0072). The rule they serve: **the summary
 * under the grid never names a case that is not on screen.**
 */

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

/** The two filter rows, level 1 and level 2 (ADR 0072). */
export interface Filters {
  origin: LibraryFilter;
  category: CategoryFilter;
}

/** What the selection screen opens on (ADR 0072): everything, on both rows.
 * Opening on a shortlist, which this once did, hides the User's own Scenarios
 * behind a filter they have to know to press — and `LibraryPicker`'s
 * `COLLAPSED_TILES` caps what is on screen anyway, so the unfiltered row is a
 * first page of the library rather than a wall of it. */
export const DEFAULT_FILTERS: Filters = { origin: "all", category: "all" };

const shows = (card: ScenarioCard, { origin, category }: Filters) =>
  matchesFilter(card, origin) && matchesCategory(card, category);

/** Where the screen opens: on the suggestions where there are any (F-62), with
 * the category row unfiltered — suggestions spread over the categories, and one
 * of them alone would often leave nothing. Otherwise the defaults above. */
export function startingFilters(scenarios: ScenarioCard[]): Filters {
  return scenarios.some((s) => s.recommendation)
    ? { origin: "recommended", category: "all" }
    : DEFAULT_FILTERS;
}

/** The Scenario to start on: the random tile (F-62), always on screen and never
 * a case the User did not choose. With nothing drawable it falls back to the
 * first card the starting filters show (else the first of all), so the summary
 * never names a card that is not on screen. */
export function firstSelectable(scenarios: ScenarioCard[]): string | null {
  if (scenarios.some(isDrawable)) return RANDOM_SCENARIO_ID;
  const filters = startingFilters(scenarios);
  return (scenarios.find((s) => shows(s, filters)) ?? scenarios[0])?.id ?? null;
}

/**
 * The cards the grid shows, sorted by name (the badge already shows origin).
 * Explicit locale so an umlaut sorts with its base letter, not after Z. The
 * random tile is not in here; the picker puts it first.
 */
export function visibleScenarios(scenarios: ScenarioCard[], filters: Filters): ScenarioCard[] {
  return scenarios
    .filter((s) => shows(s, filters))
    .sort((a, b) => a.name.localeCompare(b.name, "de"));
}

/** What a random Scenario would be drawn from (F-62): what the two filter rows
 * currently show, minus the two kinds nobody should be walked into unprepared.
 * Empty means no tile — an offer to draw where there is nothing to draw from
 * is a button that does nothing. */
export function drawPool(scenarios: ScenarioCard[], filters: Filters): ScenarioCard[] {
  return scenarios.filter((s) => isDrawable(s) && shows(s, filters));
}

/**
 * How many cards each option would yield, counted against the *other* row's
 * selection (ADR 0072). "tenant" is always counted; the picker decides whether
 * to offer it.
 */
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

/**
 * The selection after the filters changed: if the random tile is gone or the pick
 * was filtered away, fall back to the tile rather than clearing, which left the
 * summary empty. Nothing is selected only when there is nothing to fall back to.
 */
export function keptSelection(
  current: string | null,
  visible: ScenarioCard[],
  offerRandom: boolean,
): string | null {
  if (current === RANDOM_SCENARIO_ID) return offerRandom ? current : null;
  if (current !== null && visible.some((card) => card.id === current)) return current;
  return offerRandom ? RANDOM_SCENARIO_ID : null;
}
