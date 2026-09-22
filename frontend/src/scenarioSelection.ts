/**
 * What the selection screen shows of the library, and which case is picked.
 *
 * Pure functions over the cards and the two filter rows (ADR 0072), so the
 * rules can be tested without rendering a screen — the same move
 * `trainingFlow.ts` made for where a press leads. They used to be two helpers,
 * two memos, two count matrices and an effect inside `App.tsx`, where the one
 * rule every one of them serves was a comment: **the summary under the grid
 * never names a case that is not on the screen above it.**
 *
 * `useScenarioLibrary` holds the state these read; `scenarioLibrary.ts` holds
 * the routes and what a card means. This is the part in between: which cards
 * a given pair of filters leaves, and what the selection does about it.
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

/** The Scenario to start on: the random Scenario (F-62), which is the one tile
 * that stands outside both filters and is therefore always on screen. It is
 * also the only opening selection that cannot be the wrong one — every other
 * default silently proposes a case the User did not choose.
 *
 * It needs a pool to draw from, so for a library holding nothing but reverses
 * and follow-ups this falls back to the first card the starting filters show —
 * the first of all, for a library those filters leave empty — which keeps the
 * summary at the bottom of the screen from naming a card that is not on it. */
export function firstSelectable(scenarios: ScenarioCard[]): string | null {
  if (scenarios.some(isDrawable)) return RANDOM_SCENARIO_ID;
  const filters = startingFilters(scenarios);
  return (scenarios.find((s) => shows(s, filters)) ?? scenarios[0])?.id ?? null;
}

/**
 * The cards the grid shows, by name.
 *
 * By name, not by origin group: the grid badges every card with where it
 * comes from, so grouping by that said the same thing twice and left no way
 * to find a Scenario one already knows the name of. `localeCompare` with an
 * explicit locale, because an umlaut has to sort with its base letter rather
 * than after Z. The random Scenario is not in here — the picker draws it in a
 * fixed first place ahead of this list.
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
 * How many cards each option of each row would yield.
 *
 * Each row is counted against the *other* row's selection, never its own
 * (ADR 0072), so an option's number is what picking it would actually yield.
 * Every level 1 value is counted, "tenant" included: that costs nothing when
 * the caller has no company, and the picker decides whether to offer it.
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
 * The selection after the filters changed.
 *
 * A filter change can put the summary out of step with the grid two ways: the
 * random tile stops being offered, or the card that was picked is filtered
 * away. Either way the selection falls back to the tile, which is where the
 * screen opens; only with nothing left to fall back to is nothing selected.
 * Falling back rather than clearing is the point: clearing left the summary
 * empty even after the User filtered their way back to a library full of
 * cases.
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
