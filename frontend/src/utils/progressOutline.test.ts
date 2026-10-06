import { describe, expect, it } from "vitest";

import type { FocusGoal } from "../protocol";
import { measurement, session, tag } from "../test/sessions";
import { focusOutline, metricReading, recurringOutline } from "./progressOutline";
import { selectionSeries } from "./progressStats";

/** F-13, ADR 0102: the report's claims, shared by screen and PDF. */

const goal = (key: string, title = key): FocusGoal => ({
  key,
  title,
  caption: "",
  info: "",
  group: "paraverbal",
});

const input = (over: Partial<Parameters<typeof focusOutline>[0]> = {}) => ({
  goals: [],
  series: [],
  selected: [],
  readable: [],
  shows: () => true,
  ...over,
});

describe("what a focus goal reads", () => {
  it("answers every picked goal, in catalogue order", () => {
    // A vanished tile lets the user believe the goal is tracked.
    const outline = focusOutline(
      input({ goals: [goal("talk_share"), goal("empathy"), goal("training_variety")] }),
    );

    expect(outline.map((entry) => entry.key)).toEqual([
      "talk_share",
      "empathy",
      "training_variety",
    ]);
    expect(outline.every((entry) => entry.reading !== undefined)).toBe(true);
  });

  it("reads a measured goal as its figure, its own range and what it is out of", () => {
    const sessions = [
      session({ measurements: [measurement("talk_share", 40, { unit: "%" })] }),
      session({ measurements: [measurement("talk_share", 50, { unit: "%" })] }),
      session({ measurements: [measurement("talk_share", 60, { unit: "%" })] }),
      // Counted out of the readable trainings, not the points.
      session({ measurements: [] }),
    ];
    const [entry] = focusOutline(
      input({
        goals: [goal("talk_share")],
        series: selectionSeries(sessions),
        selected: sessions,
        readable: sessions,
      }),
    );

    expect(entry?.reading).toMatchObject({ kind: "metric", trainings: 3, missing: 1 });
  });

  it("names the state where a goal is measured but this selection has no value", () => {
    const [entry] = focusOutline(input({ goals: [goal("closing")] }));

    expect(entry?.reading.kind).toBe("no-value");
    expect(entry?.reading).toHaveProperty("note", expect.stringContaining("wird gemessen"));
  });

  it("lets only a goal with no measurement at all call itself unmeasured", () => {
    // "Keine Messung" only for a goal with no measurement at all.
    const sessions = [session({ feedback_goals: [tag("improvement", "empathy")] })];
    const [entry] = focusOutline(
      input({ goals: [goal("empathy")], selected: sessions, readable: sessions }),
    );

    expect(entry?.reading).toMatchObject({ kind: "mentions", measured: false, total: 1 });
  });

  it("counts mentions over the selection and not over the readable trainings", () => {
    // The length floor governs figures, not statements.
    const sessions = [
      session({ feedback_goals: [tag("improvement", "empathy")] }),
      session({ feedback_goals: [tag("strength", "empathy")] }),
    ];
    const [entry] = focusOutline(
      input({ goals: [goal("empathy")], selected: sessions, readable: [] }),
    );

    expect(entry?.reading).toMatchObject({ improvements: 1, strengths: 1, total: 2 });
  });

  it("keeps the segment goal a count of trainings and never a series", () => {
    // ADR 0081.
    const [entry] = focusOutline(input({ goals: [goal("composure")] }));

    expect(entry?.reading).toEqual({ kind: "segment", trainings: 0 });
  });

  it("sends the habit goals to the activity block rather than to a figure", () => {
    const [entry] = focusOutline(input({ goals: [goal("training_regularity")] }));

    expect(entry?.reading).toEqual({ kind: "activity", goal: "training_regularity" });
  });
});

describe("a metric's reading on its own", () => {
  it("is the same shape the overview builds when no goals are picked", () => {
    const sessions = [
      session({ measurements: [measurement("pace", 120)] }),
      session({ measurements: [measurement("pace", 130)] }),
      session({ measurements: [measurement("pace", 140)] }),
    ];
    const [series] = selectionSeries(sessions).filter((s) => s.key === "pace");
    if (!series) throw new Error("no pace series");

    expect(metricReading(series, 5)).toMatchObject({
      kind: "metric",
      trainings: 3,
      missing: 2,
    });
  });
});

describe("what recurs", () => {
  it("resolves the catalogue titles and keeps the count over its named total", () => {
    const sessions = [
      session({ feedback_goals: [tag("improvement", "closing")] }),
      session({ feedback_goals: [tag("improvement", "closing")] }),
      session({ feedback_goals: [tag("strength", "pace")] }),
    ];

    const outline = recurringOutline(sessions, [goal("closing", "Klarer Gesprächsabschluss")]);

    expect(outline.total).toBe(3);
    expect(outline.improvements).toEqual([
      { goal: "closing", title: "Klarer Gesprächsabschluss", count: 2 },
    ]);
  });

  it("leaves a retired goal's title null rather than inventing one", () => {
    // ADR 0076: retired goals keep their points but get no link.
    const sessions = [
      session({ feedback_goals: [tag("improvement", "articulation")] }),
      session({ feedback_goals: [tag("improvement", "articulation")] }),
    ];

    expect(recurringOutline(sessions, []).improvements[0]).toMatchObject({
      goal: "articulation",
      title: null,
      count: 2,
    });
  });
});
