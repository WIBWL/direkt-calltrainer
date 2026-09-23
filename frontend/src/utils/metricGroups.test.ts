import { describe, expect, it } from "vitest";

import type { ScenarioCategory } from "../scenarioLibrary";
import { GROUPS, colorOf, groupOf } from "./metricGroups";
import { PRACTICE_CATEGORY, PRACTICE_REASON } from "./practiceRoutes";

/**
 * Colour as identity on the progress view, and the editorial table behind the
 * one practice suggestion.
 *
 * Both are pure lookups, and both carry a rule that is a property of the
 * module rather than of any one value: a hue here must never be readable as a
 * verdict (ADR 0065/0078), and a goal absent from the practice table must
 * yield no suggestion rather than a default one.
 */

describe("groupOf", () => {
  it("reads the family off the aspect the schema already stores", () => {
    expect(groupOf("what")).toBe("content");
    expect(groupOf("how")).toBe("speech");
  });

  it("falls to speech for an unclassified metric, matching the backend", () => {
    expect(groupOf(null)).toBe("speech");
    expect(groupOf(undefined)).toBe("speech");
  });

  it("never returns activity, which no Kennzahl belongs to", () => {
    for (const aspect of ["how", "what", null, undefined] as const) {
      expect(groupOf(aspect)).not.toBe("activity");
    }
  });
});

describe("colorOf", () => {
  it("hands back the stylesheet's own custom property, not a literal colour", () => {
    // The palette has one home (index.css); repeating a hex here would give it two.
    expect(colorOf("how")).toBe("var(--series-speech)");
    expect(colorOf("what")).toBe("var(--series-content)");
  });

  it("takes no value, so a number can never move a hue", () => {
    // The structural half of ADR 0065: this is what separates identity colour
    // from a traffic light. `colorOf` accepts an aspect and nothing else.
    expect(colorOf.length).toBe(1);
  });

  it("declares three hues and spends none of them on red, amber or green", () => {
    const declared = Object.values(GROUPS).map((style) => style.color);

    expect(declared).toHaveLength(3);
    expect(new Set(declared).size).toBe(3);
    for (const color of declared) {
      // ADR 0078 already spent those three on the single-call traffic light.
      expect(color).not.toMatch(/red|amber|green|--light-/);
    }
  });

  it("gives every family a German heading", () => {
    for (const [group, style] of Object.entries(GROUPS)) {
      expect(style.label.length, group).toBeGreaterThan(0);
    }
  });
});

describe("PRACTICE_CATEGORY", () => {
  it("sends a goal to the kind of call it is practised in", () => {
    expect(PRACTICE_CATEGORY["needs_analysis"]).toBe("requirements");
    expect(PRACTICE_CATEGORY["objection_handling"]).toBe("closing");
    expect(PRACTICE_CATEGORY["composure"]).toBe("operations");
  });

  it("binds the paraverbal goals to no kind of call", () => {
    // Speaking rate or intonation can be worked on in any conversation, so the
    // suggestion widens their practice instead of narrowing it.
    for (const goal of ["pace", "intonation", "articulation", "conciseness", "talk_share"]) {
      expect(PRACTICE_CATEGORY[goal], goal).toBeNull();
    }
  });

  it("binds the opening to none, though the closing has a kind of its own", () => {
    expect(PRACTICE_CATEGORY["opening"]).toBeNull();
    expect(PRACTICE_CATEGORY["closing"]).toBe("closing");
  });

  it("leaves a goal it has not been told about absent, not defaulted", () => {
    // Absent means no suggestion at all, so adding a catalogue goal forces the
    // decision instead of quietly inheriting "any scenario". `undefined` and
    // `null` therefore have to stay distinguishable.
    expect("training_regularity" in PRACTICE_CATEGORY).toBe(false);
    expect(PRACTICE_CATEGORY["training_regularity"]).toBeUndefined();
    expect(PRACTICE_CATEGORY["opening"]).toBeNull();
  });

  it("names a reason for every kind of call it can route to", () => {
    const routed = Object.values(PRACTICE_CATEGORY).filter(
      (category): category is ScenarioCategory => category !== null,
    );

    for (const category of routed) {
      // A suggestion without a ground is an instruction.
      expect(PRACTICE_REASON[category], category).toBeTruthy();
    }
  });
});
