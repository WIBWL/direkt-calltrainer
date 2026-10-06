import { describe, expect, it } from "vitest";

import { FOCUS_BACKING, backingOf, goalsForMetric } from "./focusMetrics";

/** F-62, F-13, ADR 0004/0051: what a focus tile may claim. */

describe("backingOf", () => {
  it("gives an unknown goal the honest fallback rather than an empty chart", () => {
    const backing = backingOf("a-goal-nobody-has-written-down");

    expect(backing.kind).toBe("text");
    expect(backing.metrics).toEqual([]);
    // An empty note would render as a blank box.
    expect(backing.note).toMatch(/noch keine Messung/);
  });

  it("reads a measured goal's own metrics, most telling first", () => {
    expect(backingOf("active_listening")).toEqual({
      kind: "metric",
      metrics: ["interruptions", "reaction_time", "pauses"],
    });
  });

  it("keeps Souveränität a comparison and never a series", () => {
    // ADR 0081.
    expect(backingOf("composure").kind).toBe("segment");
  });

  it("knows nothing of the retired Artikulation and says so honestly", () => {
    // ADR 0111: a retired key reaches the fallback.
    const retired = backingOf("articulation");

    expect(FOCUS_BACKING.articulation).toBeUndefined();
    expect(retired.kind).toBe("text");
    expect(retired.note).toMatch(/noch keine Messung/);
  });
});

describe("the catalogue's shape", () => {
  it("backs every goal it names by exactly one of the four kinds", () => {
    for (const [goal, backing] of Object.entries(FOCUS_BACKING)) {
      expect(["metric", "activity", "text", "segment"], goal).toContain(backing.kind);
    }
  });

  it("gives metrics to the two kinds that chart them and to no others", () => {
    for (const [goal, backing] of Object.entries(FOCUS_BACKING)) {
      const charted = backing.kind === "metric" || backing.kind === "segment";
      expect(backing.metrics.length > 0, goal).toBe(charted);
    }
  });

  it("notes every goal that has no measurement, and only those", () => {
    for (const [goal, backing] of Object.entries(FOCUS_BACKING)) {
      expect(backing.note !== undefined, goal).toBe(backing.kind === "text");
    }
  });

  it("holds the split: 8 measured, 1 segment, 2 activity, 2 text", () => {
    const kinds = Object.values(FOCUS_BACKING).map((backing) => backing.kind);
    const count = (kind: string) => kinds.filter((k) => k === kind).length;

    // Pinned as counts: a goal moving between buckets changes what the screen claims.
    expect(count("metric")).toBe(8);
    expect(count("segment")).toBe(1);
    expect(count("activity")).toBe(2);
    expect(count("text")).toBe(2);
    expect(kinds).toHaveLength(13);
  });
});

describe("goalsForMetric", () => {
  it("reads the relation backwards out of the one map", () => {
    expect(goalsForMetric("interruptions")).toEqual(["active_listening"]);
    expect(goalsForMetric("closing")).toEqual(["closing"]);
  });

  it("counts only the primary metric, so a supporting figure collects nothing", () => {
    // Supporting figures collect nothing.
    expect(goalsForMetric("reaction_time")).toEqual([]);
    expect(goalsForMetric("pauses")).toEqual([]);
  });

  it("lets one metric stand behind several goals when it leads both", () => {
    expect(goalsForMetric("talk_share")).toEqual(["talk_share"]);
    expect(goalsForMetric("questions")).toEqual(["needs_analysis"]);
  });

  it("returns nothing for a metric no goal is built on", () => {
    expect(goalsForMetric("word_count")).toEqual([]);
    expect(goalsForMetric("not_a_metric")).toEqual([]);
  });

  it("keeps the segment goal off its four supporting figures but not off its first", () => {
    // pace is composure's primary metric too.
    expect(goalsForMetric("pace")).toEqual(["pace", "composure"]);
    expect(goalsForMetric("loudness")).toEqual([]);
    expect(goalsForMetric("run_length")).toEqual([]);
    expect(goalsForMetric("pauses")).toEqual([]);
  });
});
