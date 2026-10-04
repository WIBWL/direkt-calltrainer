import { describe, expect, it } from "vitest";

import type { FocusGoal } from "../protocol";
import { measurement, session, tag } from "../test/sessions";
import { focusOutline, metricReading, recurringOutline } from "./progressOutline";
import { selectionSeries } from "./progressStats";

/** What the progress report claims before anybody draws it (F-13, ADR 0102).
 * The cases pin the *claims* and not the shapes: that a goal never goes
 * unanswered, that only a goal without a measurement may say "keine Messung",
 * and that a count's denominator is the one the interface names. While the
 * screen and the file each worked the readings out for themselves they
 * disagreed, and both rendered perfectly while doing it. */

const goal = (key: string, title = key): FocusGoal => ({
  key,
  title,
  caption: "",
  info: "",
  group: "paraverbal",
});

/** Everything `focusOutline` needs, with the parts a case does not care about
 *  set to the boring answer. */
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
    // Nothing is ever dropped for having nothing to say: a tile that quietly
    // disappears lets the user believe the goal is being tracked.
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
      // A fourth training that carries no value for it: the tile says so, and
      // the count it says it out of is the readable trainings, not the points.
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
    // The case that used to fall through every branch and draw a tile holding a
    // title, a link and nothing between them.
    const [entry] = focusOutline(input({ goals: [goal("closing")] }));

    expect(entry?.reading.kind).toBe("no-value");
    expect(entry?.reading).toHaveProperty("note", expect.stringContaining("wird gemessen"));
  });

  it("lets only a goal with no measurement at all call itself unmeasured", () => {
    // "Keine Messung" is the truth for Empathie and a false claim for a metric
    // that exists and simply has no value here, which is what `measured` keeps
    // apart for both renderings at once.
    const sessions = [session({ feedback_goals: [tag("improvement", "empathy")] })];
    const [entry] = focusOutline(
      input({ goals: [goal("empathy")], selected: sessions, readable: sessions }),
    );

    expect(entry?.reading).toMatchObject({ kind: "mentions", measured: false, total: 1 });
  });

  it("counts mentions over the selection and not over the readable trainings", () => {
    // A statement is a statement whatever the call's length: the length floor
    // governs figures, not what a wrap-up wrote.
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
    // ADR 0081: a line through it would be the difference over time, the one
    // number this goal must not have.
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
    // The overview used to render its own, against a count that made the "no
    // value in N trainings" line unreachable there.
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
    // Its points still point at it (ADR 0076 deactivates rather than deletes),
    // and a row whose title is unknown must not link to a page that can only
    // say the name means nothing.
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
