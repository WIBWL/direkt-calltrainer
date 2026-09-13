import { describe, expect, it } from "vitest";

import { briefingFollows, nextScreen, type FlowContext } from "./trainingFlow";

/**
 * The training flow's transition table.
 *
 * Worth testing where the rest of the frontend is not: the machine has nine
 * screens and ten events, it used to be fourteen `setScreen` calls that could
 * only be read by finding every one of them, and `tsc` can see that a
 * transition returns *a* screen but not that it returns the right one.
 *
 * No React, no harness: everything the flow routes on is passed in, which is
 * the whole point of keeping it pure.
 */

/** An ordinary call: not a reverse, not drawn, a case with something in it. */
const BASE: FlowContext = {
  reverse: false,
  drawn: false,
  committedCase: { briefing: "Sie sind im Support.", facts: null },
  reducedMotion: false,
  skipMicCheck: false,
  stored: true,
};

const ctx = (over: Partial<FlowContext> = {}): FlowContext => ({ ...BASE, ...over });

describe("committing to a pairing", () => {
  it("goes to the microphone check", () => {
    expect(nextScreen(ctx(), "sessionCommitted")).toEqual({
      screen: "mic-check",
      cut: "none",
    });
  });

  it("skips the check but never the case, coming out of a finished training", () => {
    expect(nextScreen(ctx({ skipMicCheck: true }), "sessionCommitted").screen)
      .toBe("case-brief");
  });

  it("sends a reverse to its own briefing", () => {
    expect(nextScreen(ctx({ skipMicCheck: true, reverse: true }), "sessionCommitted").screen)
      .toBe("brief");
  });
});

describe("confirming the microphone check", () => {
  it("stops at the case", () => {
    expect(nextScreen(ctx(), "micConfirmed")).toEqual({
      screen: "case-brief",
      cut: "none",
    });
  });

  it("turns the card over for a reverse", () => {
    expect(nextScreen(ctx({ reverse: true }), "micConfirmed")).toEqual({
      screen: "brief",
      cut: "reverse",
    });
  });

  it("throws the die for a drawn Scenario", () => {
    expect(nextScreen(ctx({ drawn: true }), "micConfirmed")).toEqual({
      screen: "rolling",
      cut: "none",
    });
  });

  it("skips the throw under reduced motion, since the die is all it had to say", () => {
    expect(nextScreen(ctx({ drawn: true, reducedMotion: true }), "micConfirmed")).toEqual({
      screen: "incoming",
      cut: "fade",
    });
  });

  it("goes straight to the phone when the case holds nothing to read", () => {
    const empty = ctx({ committedCase: { briefing: null, facts: null } });
    expect(nextScreen(empty, "micConfirmed").screen).toBe("incoming");
  });

  it("stops at the case while it is still being fetched", () => {
    // Null is not "nothing": skipping a case that turns out to hold something
    // cannot be undone, so the safe answer is to stop. `caseArrivedEmpty`
    // moves on a moment later if it turns out to be empty.
    expect(nextScreen(ctx({ committedCase: null }), "micConfirmed").screen)
      .toBe("case-brief");
  });

  it("stops at the case for facts alone, with no briefing", () => {
    const factsOnly = ctx({ committedCase: { briefing: null, facts: "Vertrag läuft aus." } });
    expect(nextScreen(factsOnly, "micConfirmed").screen).toBe("case-brief");
  });
});

describe("the button's label", () => {
  /**
   * The defect this module was extracted to remove.
   *
   * The router read the briefing off the *committed case*; the label read it
   * off the *library card*. A Scenario carrying facts but no card briefing
   * therefore promised a call and delivered a page of text — the exact failure
   * `MicCheck`'s own docstring names. Both now ask this function.
   */
  it("agrees with where the press actually leads, for every context", () => {
    const cases: FlowContext[] = [
      ctx(),
      ctx({ reverse: true }),
      ctx({ drawn: true }),
      ctx({ drawn: true, reducedMotion: true }),
      ctx({ committedCase: null }),
      ctx({ committedCase: { briefing: null, facts: null } }),
      ctx({ committedCase: { briefing: null, facts: "Vertrag läuft aus." } }),
      ctx({ committedCase: { briefing: "Sie sind im Vertrieb.", facts: null } }),
    ];
    for (const context of cases) {
      const { screen } = nextScreen(context, "micConfirmed");
      const isBriefing = screen === "brief" || screen === "case-brief";
      expect(briefingFollows(context)).toBe(isBriefing);
    }
  });

  it("promises a briefing for facts without a card briefing", () => {
    // The regression itself: this combination used to read "start the call".
    const factsOnly = ctx({ committedCase: { briefing: null, facts: "Vertrag läuft aus." } });
    expect(briefingFollows(factsOnly)).toBe(true);
  });
});

describe("the way out of a call", () => {
  it("waits for a wrap-up that is coming", () => {
    expect(nextScreen(ctx({ stored: true }), "callEnded").screen).toBe("analysing");
  });

  it("goes straight to the transcript when nothing was stored (ADR 0066)", () => {
    expect(nextScreen(ctx({ stored: false }), "callEnded").screen).toBe("transcript");
  });
});

describe("reaching the call", () => {
  it("is only possible by accepting it", () => {
    // The three things App does on the way in -- unmute, activate playback,
    // send session.activate -- hang off this one event. Nothing else may
    // return "call", or they could be bypassed.
    const events = [
      "sessionCommitted",
      "micConfirmed",
      "caseArrivedEmpty",
      "caseRead",
      "rollFinished",
      "callEnded",
      "analysed",
      "micCheckCancelled",
      "restarted",
    ] as const;
    for (const event of events) {
      expect(nextScreen(ctx(), event).screen).not.toBe("call");
    }
    expect(nextScreen(ctx(), "callAccepted").screen).toBe("call");
  });
});

describe("the ways back to the start", () => {
  it("abandoning the check and restarting both land on setup", () => {
    expect(nextScreen(ctx(), "micCheckCancelled").screen).toBe("setup");
    expect(nextScreen(ctx(), "restarted").screen).toBe("setup");
  });
});
