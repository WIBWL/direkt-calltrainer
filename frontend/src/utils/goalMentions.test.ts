import { describe, expect, it } from "vitest";

import { session, tag } from "../test/sessions";
import { MIN_MENTIONS, mentionSummary, mentionsFor, statementsFor } from "./goalMentions";

/**
 * Counting what the wrap-ups said (ADR 0080, the dashboard's block D).
 *
 * This is the arithmetic most easily misread on the whole screen: it produces a
 * count over a denominator, and a count over a denominator is one careless
 * change away from being a score. The cases below pin the three decisions that
 * keep it a frequency of statements — counted per training, divided by the
 * trainings that could have said something, and shown only from a real
 * threshold — plus the ordering, which has to be stable or the same data
 * renders differently on two reads.
 *
 * A wrong denominator here does not fail anywhere. It writes "in 4 von 6
 * Auswertungen genannt" where the truth is 4 of 9, and the user has no way to
 * check it.
 */

describe("the denominator", () => {
  it("counts only the trainings whose wrap-up carried an assignment", () => {
    // A training with no wrap-up never had an opinion, and one written before
    // the assignment existed could not record it. Counting either in would
    // quietly shrink every fraction on the screen.
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
    // Two improvements about the closing in one call are one call that
    // mentioned it. Counting points would let a single wordy wrap-up look like
    // a pattern.
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
    // A goal named as a strength in one call and as an improvement in another
    // is two different statements, and one call can carry both.
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
    // One point from one training is an observation, not a pattern, and
    // presenting it as one is the failure this block has to avoid.
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
    // "What keeps coming up" is a different question from "everything that was
    // ever said".
    const goals = ["a", "b", "c", "d", "e"];
    const sessions = [
      session({ feedback_goals: goals.map((g) => tag("improvement", g)) }),
      session({ feedback_goals: goals.map((g) => tag("improvement", g)) }),
    ];

    expect(mentionSummary(sessions).improvements).toHaveLength(3);
  });

  it("orders by count and breaks a tie by goal key", () => {
    // Two goals mentioned three times each must not swap places because a
    // training was added at the other end of the list.
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
