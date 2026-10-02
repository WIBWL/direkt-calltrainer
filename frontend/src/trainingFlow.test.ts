import { describe, expect, it } from "vitest";

import { briefingFollows, nextScreen, type FlowContext, type FlowEvent } from "./trainingFlow";

/**
 * The training flow's transition table. `tsc` sees that a transition returns
 * *a* screen, not the right one. No React, no harness: everything the flow
 * routes on is passed in.
 */

/** An ordinary call: not a reverse, not drawn, a case with something in it. */
const BASE: FlowContext = {
  reverse: false,
  drawn: false,
  committedCase: { briefing: "Sie sind im Support.", facts: null },
  reducedMotion: false,
};

const ctx = (over: Partial<FlowContext> = {}): FlowContext => ({ ...BASE, ...over });

/** An ordinary commit from the setup screen: not a reverse, check not skipped. */
const commit = (over: { reverse?: boolean; skipMicCheck?: boolean } = {}): FlowEvent => ({
  type: "sessionCommitted",
  reverse: false,
  skipMicCheck: false,
  ...over,
});
const MIC_CONFIRMED: FlowEvent = { type: "micConfirmed" };

describe("committing to a pairing", () => {
  it("goes to the microphone check", () => {
    expect(nextScreen(ctx(), commit())).toEqual({
      screen: "mic-check",
      cut: "none",
    });
  });

  it("skips the check but never the case, coming out of a finished training", () => {
    expect(nextScreen(ctx(), commit({ skipMicCheck: true })).screen).toBe("case-brief");
  });

  it("sends a reverse to its own briefing", () => {
    expect(nextScreen(ctx(), commit({ skipMicCheck: true, reverse: true })).screen)
      .toBe("brief");
  });

  it("keeps the check for a reverse picked from the library", () => {
    expect(nextScreen(ctx(), commit({ reverse: true })).screen).toBe("mic-check");
  });

  it("reads the commit's facts off the event, not off a context still behind it", () => {
    // The press that commits is the one that sets the committed Session, so
    // render state says "not a reverse" at that moment. The event decides.
    expect(nextScreen(ctx({ reverse: false }), commit({ skipMicCheck: true, reverse: true })).screen)
      .toBe("brief");
  });

  it("does not compile without the facts only the committing handler knows", () => {
    // @ts-expect-error -- a commit must say whether it skips the check
    const incomplete: FlowEvent = { type: "sessionCommitted", reverse: false };
    // @ts-expect-error -- an ended call must say whether it was stored
    const unstored: FlowEvent = { type: "callEnded" };
    expect([incomplete, unstored]).toHaveLength(2);
  });
});

describe("confirming the microphone check", () => {
  it("stops at the case", () => {
    expect(nextScreen(ctx(), MIC_CONFIRMED)).toEqual({
      screen: "case-brief",
      cut: "none",
    });
  });

  it("sends a reverse to its briefing", () => {
    expect(nextScreen(ctx({ reverse: true }), MIC_CONFIRMED)).toEqual({
      screen: "brief",
      cut: "none",
    });
  });

  it("throws the die for a drawn Scenario", () => {
    expect(nextScreen(ctx({ drawn: true }), MIC_CONFIRMED)).toEqual({
      screen: "rolling",
      cut: "none",
    });
  });

  it("skips the throw under reduced motion, since the die is all it had to say", () => {
    expect(nextScreen(ctx({ drawn: true, reducedMotion: true }), MIC_CONFIRMED)).toEqual({
      screen: "incoming",
      cut: "fade",
    });
  });

  it("goes straight to the phone when the case holds nothing to read", () => {
    const empty = ctx({ committedCase: { briefing: null, facts: null } });
    expect(nextScreen(empty, MIC_CONFIRMED).screen).toBe("incoming");
  });

  it("stops at the case while it is still being fetched", () => {
    // Null is not "nothing": skipping a case that turns out to hold something
    // cannot be undone, so the safe answer is to stop. `caseArrivedEmpty`
    // moves on a moment later if it turns out to be empty.
    expect(nextScreen(ctx({ committedCase: null }), MIC_CONFIRMED).screen)
      .toBe("case-brief");
  });

  it("stops at the case for facts alone, with no briefing", () => {
    const factsOnly = ctx({ committedCase: { briefing: null, facts: "Vertrag läuft aus." } });
    expect(nextScreen(factsOnly, MIC_CONFIRMED).screen).toBe("case-brief");
  });
});

describe("the button's label", () => {
  /**
   * The defect this module was extracted to remove: label and router read
   * different sources, so the label promised a call and delivered a page of
   * text (see `MicCheck`). Both now ask this function.
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
      const { screen } = nextScreen(context, MIC_CONFIRMED);
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
    expect(nextScreen(ctx(), { type: "callEnded", stored: true }).screen).toBe("analysing");
  });

  it("goes straight to the transcript when nothing was stored (ADR 0066)", () => {
    expect(nextScreen(ctx(), { type: "callEnded", stored: false }).screen).toBe("transcript");
  });
});

describe("reaching the call", () => {
  it("is only possible by accepting it", () => {
    // The three things App does on the way in -- unmute, activate playback,
    // send session.activate -- hang off this one event. Nothing else may
    // return "call", or they could be bypassed.
    const events: FlowEvent[] = [
      commit(),
      commit({ skipMicCheck: true }),
      commit({ skipMicCheck: true, reverse: true }),
      MIC_CONFIRMED,
      { type: "caseArrivedEmpty" },
      { type: "caseRead" },
      { type: "rollFinished" },
      { type: "callEnded", stored: true },
      { type: "callEnded", stored: false },
      { type: "analysed" },
      { type: "micCheckCancelled" },
      { type: "restarted" },
    ];
    for (const event of events) {
      expect(nextScreen(ctx(), event).screen).not.toBe("call");
    }
    expect(nextScreen(ctx(), { type: "callAccepted" }).screen).toBe("call");
  });
});

describe("the ways back to the start", () => {
  it("abandoning the check and restarting both land on setup", () => {
    expect(nextScreen(ctx(), { type: "micCheckCancelled" }).screen).toBe("setup");
    expect(nextScreen(ctx(), { type: "restarted" }).screen).toBe("setup");
  });
});
