import { describe, expect, it } from "vitest";

import { FOCUS_BACKING, backingOf, goalsForMetric } from "./focusMetrics";

/**
 * What a focus tile is allowed to claim (F-62, F-13). A goal in the wrong bucket
 * renders fine but may claim a measurement that does not exist, which
 * ADR 0004/0051 rule out.
 */

describe("backingOf", () => {
  it("gives an unknown goal the honest fallback rather than an empty chart", () => {
    const backing = backingOf("a-goal-nobody-has-written-down");

    expect(backing.kind).toBe("text");
    expect(backing.metrics).toEqual([]);
    // The tile has to say *why* there is no chart; an empty note would render
    // as a blank box under a heading.
    expect(backing.note).toMatch(/noch keine Messung/);
  });

  it("reads a measured goal's own metrics, most telling first", () => {
    expect(backingOf("active_listening")).toEqual({
      kind: "metric",
      metrics: ["interruptions", "reaction_time", "pauses"],
    });
  });

  it("keeps Souveränität a comparison and never a series", () => {
    // ADR 0081: a line through it would be the difference over time, which is
    // the one number this goal must not have.
    expect(backingOf("composure").kind).toBe("segment");
  });

  it("says of Artikulation that no measurement is planned, not merely absent", () => {
    const planned = backingOf("articulation").note;
    const absent = backingOf("empathy").note;

    expect(planned).toMatch(/keine Messung, und es ist keine geplant/);
    expect(absent).not.toBe(planned);
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

  it("holds the split the dashboard concept states: 8 measured, 1 segment, 2 activity, 3 text", () => {
    const kinds = Object.values(FOCUS_BACKING).map((backing) => backing.kind);
    const count = (kind: string) => kinds.filter((k) => k === kind).length;

    // docs/dashboard-concept.md section 4.2. Pinned as a count because the
    // honest answer differs per goal, and a goal quietly moving between
    // buckets is what changes what the screen claims.
    expect(count("metric")).toBe(8);
    expect(count("segment")).toBe(1);
    expect(count("activity")).toBe(2);
    expect(count("text")).toBe(3);
    expect(kinds).toHaveLength(14);
  });
});

describe("goalsForMetric", () => {
  it("reads the relation backwards out of the one map", () => {
    expect(goalsForMetric("interruptions")).toEqual(["active_listening"]);
    expect(goalsForMetric("closing")).toEqual(["closing"]);
  });

  it("counts only the primary metric, so a supporting figure collects nothing", () => {
    // reaction_time and pauses sit behind active_listening, but a sentence
    // about listening does not belong under every figure it was read from.
    expect(goalsForMetric("reaction_time")).toEqual([]);
    expect(goalsForMetric("pauses")).toEqual([]);
  });

  it("lets one metric stand behind several goals when it leads both", () => {
    // talk_share leads its own goal; needs_analysis leads with questions.
    expect(goalsForMetric("talk_share")).toEqual(["talk_share"]);
    expect(goalsForMetric("questions")).toEqual(["needs_analysis"]);
  });

  it("returns nothing for a metric no goal is built on", () => {
    expect(goalsForMetric("word_count")).toEqual([]);
    expect(goalsForMetric("not_a_metric")).toEqual([]);
  });

  it("keeps the segment goal off its four supporting figures but not off its first", () => {
    // composure names five metrics and `pace` is the first of them, so the
    // Sprechtempo page carries statements about Souveränität as well as about
    // Sprechtempo. That follows from the primary-only rule rather than working
    // around it: the four figures behind the comparison collect nothing.
    expect(goalsForMetric("pace")).toEqual(["pace", "composure"]);
    expect(goalsForMetric("loudness")).toEqual([]);
    expect(goalsForMetric("run_length")).toEqual([]);
    expect(goalsForMetric("pauses")).toEqual([]);
  });
});
