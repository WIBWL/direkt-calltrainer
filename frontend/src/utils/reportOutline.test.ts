import { describe, expect, it } from "vitest";

import type { FocusGoal, Measurement, SessionFeedback, SessionTurn } from "../protocol";
import { callMeta, metricGroups, reportOutline } from "./reportOutline";

/**
 * The feedback report's outline — what the page and the downloaded file both
 * say (F-64). These pin the parts the two used to decide separately and got
 * wrong in one of them: a point's moment, its focus goal, which side of the
 * call the User was on, and which half a metric is read in.
 */

function turn(turn_id: number, start_offset_ms: number): SessionTurn {
  return {
    turn_id,
    speaker: "user",
    start_offset_ms,
    duration_ms: 1000,
    transcript: "Guten Tag.",
    interrupted: false,
    unheard_text: null,
  };
}

function goal(key: string, title: string): FocusGoal {
  return { key, title, caption: "", info: "", group: "phases" };
}

function measurement(key: string, aspect: Measurement["aspect"], detail = null): Measurement {
  return { key, name: key, unit: null, aspect, value: 1, detail };
}

const feedback: SessionFeedback = {
  summary: "Das Gespräch endete mit einem Termin.",
  phase_language: "Warm eröffnet.",
  tone_fit: null,
  points: [
    { kind: "strength", text: "Klar begrüßt.", turn_id: 1, goal: "opening" },
    { kind: "improvement", text: "Früher zusammenfassen.", turn_id: 2, goal: "retired_goal" },
    { kind: "improvement", text: "Mehr fragen.", turn_id: null, goal: null },
  ],
};

describe("reportOutline", () => {
  const outline = reportOutline({
    personaName: "Thomas Brandt",
    scenarioName: "Störung im Betrieb",
    feedback,
    turns: [turn(1, 4000), turn(2, 61000)],
    goals: [goal("opening", "Gesprächseinstieg")],
  });

  it("resolves a point to the moment it cites and names its goal", () => {
    expect(outline.wrapUp?.strengths).toEqual([
      { text: "Klar begrüßt.", offsetMs: 4000, goal: "Gesprächseinstieg" },
    ]);
  });

  it("leaves a retired goal and a missing citation empty rather than showing a key", () => {
    expect(outline.wrapUp?.improvements).toEqual([
      { text: "Früher zusammenfassen.", offsetMs: 61000, goal: null },
      { text: "Mehr fragen.", offsetMs: null, goal: null },
    ]);
  });

  it("treats a cited Turn that is not in the transcript as no citation", () => {
    const orphan = reportOutline({
      personaName: "Thomas Brandt",
      feedback: { ...feedback, points: [{ kind: "strength", text: "x", turn_id: 9, goal: null }] },
      turns: [turn(1, 4000)],
    });
    expect(orphan.wrapUp?.strengths[0]?.offsetMs).toBeNull();
  });

  it("has no wrap-up without feedback, and still says which call it was", () => {
    const bare = reportOutline({ personaName: "Thomas Brandt", scenarioName: "Störung im Betrieb" });
    expect(bare.wrapUp).toBeNull();
    expect(bare.meta).toEqual({
      scenario: "Störung im Betrieb",
      partner: "Thomas Brandt",
      reversal: null,
    });
  });
});

describe("callMeta", () => {
  it("says which side the User was on in a reverse", () => {
    expect(callMeta("Thomas Brandt", null, true)).toEqual({
      scenario: null,
      partner: "Thomas Brandt",
      reversal: "Sie riefen an, Thomas Brandt nahm ab",
    });
  });
});

describe("metricGroups", () => {
  it("keeps both halves, an empty one included, and files an unclassified metric under 'what'", () => {
    const groups = metricGroups([measurement("pace", "how"), measurement("retired", null)]);
    expect(groups.map((group) => [group.aspect, group.measurements.map((m) => m.key)])).toEqual([
      ["how", ["pace"]],
      ["what", ["retired"]],
    ]);
  });
});
