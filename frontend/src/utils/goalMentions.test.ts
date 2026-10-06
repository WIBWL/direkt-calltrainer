import { describe, expect, it } from "vitest";

import { session, tag } from "../test/sessions";
import { MIN_MENTIONS, mentionSummary, mentionsFor, statementsFor } from "./goalMentions";

/** ADR 0080: a frequency, not a score; a wrong denominator fails nowhere. */

describe("the denominator", () => {
  it("counts only the trainings whose wrap-up carried an assignment", () => {
    // Untagged trainings could not have named it.
    const summary = mentionSummary([
      session({ feedback_goals: [tag("improvement", "closing")] }),
      session({ feedback_goals: [tag("improvement", "closing")] }),
      session({ feedback_goals: [], has_feedback: false, feedback_status: "failed" }),
      session({ feedback_goals: [] }),
    ]);

    expect(summary.total).toBe(2);
    expect(summary.improvements).toEqual([{ goal: "closing", count: 2 }]);
  });

  it("is the same denominator on a focus tile as in the recurring block", () => {
    const sessions = [
      session({ feedback_goals: [tag("improvement", "closing")] }),
      session({ feedback_goals: [tag("strength", "empathy")] }),
      session({ feedback_goals: [] }),
    ];

    expect(mentionsFor(sessions, "closing").total).toBe(mentionSummary(sessions).total);
  });
});

describe("counting a mention", () => {
  it("counts a training once however often the wrap-up named the goal", () => {
    // Per training: one wordy wrap-up is no pattern.
    const summary = mentionSummary([
      session({
        feedback_goals: [
          tag("improvement", "closing", "Der Abschluss blieb offen."),
          tag("improvement", "closing", "Kein nächster Schritt vereinbart."),
        ],
      }),
      session({ feedback_goals: [tag("improvement", "closing")] }),
    ]);

    expect(summary.improvements).toEqual([{ goal: "closing", count: 2 }]);
  });

  it("keeps the two kinds apart in one training", () => {
    const tally = mentionsFor(
      [
        session({
          feedback_goals: [tag("strength", "pace"), tag("improvement", "pace")],
        }),
      ],
      "pace",
    );

    expect(tally).toEqual({ strengths: 1, improvements: 1, total: 1 });
  });

  it("says nothing about a goal no wrap-up named", () => {
    const tally = mentionsFor([session({ feedback_goals: [tag("strength", "pace")] })], "empathy");
    expect(tally).toMatchObject({ strengths: 0, improvements: 0, total: 1 });
  });
});

describe("what counts as recurring", () => {
  it("leaves out a goal named only once", () => {
    const summary = mentionSummary([session({ feedback_goals: [tag("improvement", "closing")] })]);
    expect(summary.improvements).toEqual([]);
  });

  it("takes it from the second mention", () => {
    const sessions = Array.from({ length: MIN_MENTIONS }, () =>
      session({ feedback_goals: [tag("improvement", "closing")] }),
    );
    expect(mentionSummary(sessions).improvements).toHaveLength(1);
  });

  it("shows at most three per column", () => {
    const goals = ["a", "b", "c", "d", "e"];
    const sessions = [
      session({ feedback_goals: goals.map((g) => tag("improvement", g)) }),
      session({ feedback_goals: goals.map((g) => tag("improvement", g)) }),
    ];

    expect(mentionSummary(sessions).improvements).toHaveLength(3);
  });

  it("orders by count and breaks a tie by goal key", () => {
    // Ties must not swap when a training is added.
    const sessions = [
      session({ feedback_goals: [tag("improvement", "zebra"), tag("improvement", "alpha")] }),
      session({ feedback_goals: [tag("improvement", "zebra"), tag("improvement", "alpha")] }),
      session({ feedback_goals: [tag("improvement", "zebra")] }),
    ];

    expect(mentionSummary(sessions).improvements).toEqual([
      { goal: "zebra", count: 3 },
      { goal: "alpha", count: 2 },
    ]);
  });

  it("keeps strengths and improvements in separate columns", () => {
    const sessions = [
      session({ feedback_goals: [tag("strength", "pace"), tag("improvement", "closing")] }),
      session({ feedback_goals: [tag("strength", "pace"), tag("improvement", "closing")] }),
    ];
    const summary = mentionSummary(sessions);

    expect(summary.strengths.map((s) => s.goal)).toEqual(["pace"]);
    expect(summary.improvements.map((s) => s.goal)).toEqual(["closing"]);
  });
});

describe("the sentences behind the count", () => {
  it("quotes the wrap-up verbatim, with the training it was written in", () => {
    const statements = statementsFor(
      [
        session({
          session_id: "abc",
          scenario: "Preisgespräch",
          feedback_goals: [tag("improvement", "closing", "Der Abschluss blieb offen.")],
        }),
      ],
      ["closing"],
    );

    expect(statements).toEqual([
      {
        sessionId: "abc",
        at: "2026-09-01T10:00:00Z",
        scenario: "Preisgespräch",
        persona: "Thomas Brandt",
        kind: "improvement",
        goal: "closing",
        text: "Der Abschluss blieb offen.",
      },
    ]);
  });

  it("collects several goals at once, since a metric can stand behind more than one", () => {
    const statements = statementsFor(
      [
        session({
          feedback_goals: [
            tag("improvement", "pace"),
            tag("strength", "active_listening"),
            tag("strength", "empathy"),
          ],
        }),
      ],
      ["pace", "active_listening"],
    );

    expect(statements.map((s) => s.goal)).toEqual(["pace", "active_listening"]);
  });

  it("keeps the newest training first and the wrap-up's own order within it", () => {
    const statements = statementsFor(
      [
        session({
          started_at: "2026-09-05T10:00:00Z",
          feedback_goals: [
            tag("improvement", "closing", "zweitens"),
            tag("strength", "closing", "drittens"),
          ],
        }),
        session({
          started_at: "2026-09-01T10:00:00Z",
          feedback_goals: [tag("improvement", "closing", "viertens")],
        }),
      ],
      ["closing"],
    );

    expect(statements.map((s) => s.text)).toEqual(["zweitens", "drittens", "viertens"]);
  });
});
