import { describe, expect, it } from "vitest";

import { RANDOM_SCENARIO_ID, type ScenarioCard } from "./scenarioLibrary";
import {
  DEFAULT_FILTERS,
  drawPool,
  filterCounts,
  firstSelectable,
  keptSelection,
  startingFilters,
  visibleScenarios,
} from "./scenarioSelection";

/**
 * What the selection screen shows, and what stays picked. Every rule serves one
 * promise: the summary names a case that is on screen. None fails loudly — a
 * wrong one renders a fine screen pointing at an invisible card.
 */

function card(id: string, overrides: Partial<ScenarioCard> = {}): ScenarioCard {
  return {
    id,
    name: id,
    short_description: "",
    briefing: "",
    category: "operations",
    origin: "builtin",
    shared: false,
    follow_up: false,
    reverse: false,
    origin_session: null,
    recommendation: null,
    ...overrides,
  };
}

const suggested = { call_type: true, goals: [] };

describe("where the screen opens", () => {
  it("opens on the suggestions where there are any (F-62)", () => {
    const library = [card("a"), card("b", { recommendation: suggested })];
    expect(startingFilters(library)).toEqual({ origin: "recommended", category: "all" });
  });

  it("opens on everything otherwise, never on a shortlist (ADR 0072)", () => {
    expect(startingFilters([card("a")])).toEqual(DEFAULT_FILTERS);
  });

  it("picks the random tile first, the one choice that cannot be the wrong one", () => {
    expect(firstSelectable([card("a"), card("b")])).toBe(RANDOM_SCENARIO_ID);
  });

  it("picks the first shown card where nothing can be drawn", () => {
    // Nothing but a reverse and a follow-up: no pool, no random tile.
    const library = [card("r", { reverse: true, origin: "own" }), card("f", { follow_up: true, origin: "own" })];
    expect(firstSelectable(library)).toBe("r");
  });

  it("selects nothing in an empty library", () => {
    expect(firstSelectable([])).toBeNull();
  });
});

describe("what the grid shows", () => {
  it("sorts by name, an umlaut with its base letter", () => {
    const library = [card("Zahlung"), card("Übergabe"), card("Anruf")];
    expect(visibleScenarios(library, DEFAULT_FILTERS).map((c) => c.id)).toEqual([
      "Anruf",
      "Übergabe",
      "Zahlung",
    ]);
  });

  it("applies both rows at once", () => {
    const library = [
      card("a", { category: "pricing" }),
      card("b", { category: "pricing", origin: "own" }),
      card("c", { category: "closing" }),
    ];
    const shown = visibleScenarios(library, { origin: "standard", category: "pricing" });
    expect(shown.map((c) => c.id)).toEqual(["a"]);
  });
});

describe("what a random Scenario is drawn from", () => {
  it("never a reverse or a follow-up, which cannot be walked into unread", () => {
    const library = [card("a"), card("r", { reverse: true }), card("f", { follow_up: true })];
    expect(drawPool(library, DEFAULT_FILTERS).map((c) => c.id)).toEqual(["a"]);
  });

  it("only what the chips on screen show", () => {
    const library = [card("a", { category: "pricing" }), card("b", { category: "closing" })];
    expect(drawPool(library, { origin: "all", category: "closing" }).map((c) => c.id)).toEqual(["b"]);
  });
});

describe("the counts on the chips (ADR 0072)", () => {
  const library = [
    card("a", { category: "pricing" }),
    card("b", { category: "pricing", origin: "own" }),
    card("c", { category: "closing" }),
  ];

  it("count each row against the other row's selection, not its own", () => {
    const counts = filterCounts(library, { origin: "standard", category: "pricing" });

    // Origin options, under the pricing category.
    expect(counts.origin.all).toBe(2);
    expect(counts.origin.standard).toBe(1);
    expect(counts.origin.own).toBe(1);
    // Category options, under the standard origin.
    expect(counts.category.all).toBe(2);
    expect(counts.category.pricing).toBe(1);
    expect(counts.category.closing).toBe(1);
  });

  it("say what picking an option would show", () => {
    const filters = { origin: "all" as const, category: "closing" as const };
    const counts = filterCounts(library, filters);
    expect(counts.origin.standard).toBe(
      visibleScenarios(library, { ...filters, origin: "standard" }).length,
    );
  });
});

describe("the selection after a filter change", () => {
  const visible = [card("a"), card("b")];

  it("keeps a card that is still on screen", () => {
    expect(keptSelection("a", visible, true)).toBe("a");
  });

  it("falls back to the random tile when the picked card is filtered away", () => {
    expect(keptSelection("gone", visible, true)).toBe(RANDOM_SCENARIO_ID);
  });

  it("keeps the random tile while it is offered", () => {
    expect(keptSelection(RANDOM_SCENARIO_ID, visible, true)).toBe(RANDOM_SCENARIO_ID);
  });

  it("drops the random tile when there is nothing left to draw", () => {
    expect(keptSelection(RANDOM_SCENARIO_ID, visible, false)).toBeNull();
  });

  it("selects nothing rather than a card off screen", () => {
    expect(keptSelection("gone", visible, false)).toBeNull();
  });

  it("comes back to the tile once the User filters their way back", () => {
    // Clearing rather than falling back used to leave the summary empty even
    // after the library was full of cases again.
    expect(keptSelection(null, visible, true)).toBe(RANDOM_SCENARIO_ID);
  });
});
