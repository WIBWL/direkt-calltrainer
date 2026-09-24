/**
 * Where a press leads: the training flow's screens and transitions as one pure
 * table, testable without WebSocket, AudioContext or ONNX. Decides *where* and *how
 * covered*, never side effects (playback, `session.activate`, unmute stay in App.tsx).
 */

/** The screens of the training flow, in the order they are normally met. */
export type Screen =
  | "setup"
  | "mic-check"
  /** The trainee's own briefing and the facts of the case, between the check
   * and the ringing phone. The reverse's equivalent is "brief". */
  | "case-brief"
  | "brief"
  | "rolling"
  | "incoming"
  | "call"
  /** The wait for the wrap-up, which is written in the worker (ADR 0049) and
   * is therefore not there the moment the call ends. Skipped where nothing is
   * on the way: a Session that was not stored has no wrap-up coming
   * (ADR 0066). */
  | "analysing"
  | "transcript";

/** What covers a transition, if anything. Named here rather than at the call
 * sites because which cut covers a change of screen is part of the same
 * decision as where it goes (`components/ScreenTransition.tsx` performs it). */
export type Cut = "none" | "fade";

/**
 * What render state and environment answer at any press, passed in so the table
 * stays testable. A fact only one handler knows rides on its event instead: as a
 * context field a forgotten override silently misrouted; on the event it won't compile.
 */
export interface FlowContext {
  /** The committed Scenario replays a finished Session with the roles swapped
   * (ADR 0070), so it goes to its own briefing rather than to the phone. */
  reverse: boolean;
  /** A random Scenario was drawn (F-62): it is thrown for, and its case is
   * deliberately not read beforehand. */
  drawn: boolean;
  /**
   * The committed case from the detail route, null while in flight. Null routes
   * to the briefing screen, the safe answer: an empty case moves on by itself
   * (`caseArrivedEmpty`), a skipped full one cannot be undone.
   */
  committedCase: { briefing: string | null; facts: string | null } | null;
  /** Whether the User asked for reduced motion. The die has nothing to say
   * standing still, so under it the throw is skipped rather than shown. */
  reducedMotion: boolean;
}

/** What happened, as the flow hears it. */
export type FlowEvent =
  /**
   * A pairing was committed and the Session is connecting (ADR 0042). Facts come
   * from the handler, as render state has not caught up yet. `skipMicCheck` is
   * true straight from a finished training (F-60/F-61).
   */
  | { type: "sessionCommitted"; reverse: boolean; skipMicCheck: boolean }
  /** The microphone check was confirmed. */
  | { type: "micConfirmed" }
  /** The case arrived and holds nothing to read, on a screen already showing
   * it. Only reachable for a way in that commits before its case is fetched. */
  | { type: "caseArrivedEmpty" }
  /** The User read the case and pressed on. */
  | { type: "caseRead" }
  /** The die finished rolling. */
  | { type: "rollFinished" }
  /**
   * The ringing phone answered, or a reverse's briefing confirmed (there the
   * User is the caller, `_casting` in `session/prompting.py`). The only event
   * that reaches the call, so what `App` does on the way in cannot be bypassed.
   */
  | { type: "callAccepted" }
  /** The call ended, by hang-up, error or the Persona saying goodbye.
   * `stored`: the Session was written, and so has a wrap-up coming. */
  | { type: "callEnded"; stored: boolean }
  /** The wrap-up settled, or the User would rather not wait for it. */
  | { type: "analysed" }
  /** The microphone check was abandoned, dropping the committed Session. */
  | { type: "micCheckCancelled" }
  /** Back to the beginning from the end of a training. */
  | { type: "restarted" };

export interface Transition {
  screen: Screen;
  cut: Cut;
}

/**
 * Where an event leads, and what covers the change. The switch is exhaustive so
 * a new event does not compile until its destination and cut are decided.
 */
export function nextScreen(context: FlowContext, event: FlowEvent): Transition {
  switch (event.type) {
    case "sessionCommitted":
      // The check is skipped coming out of a finished training, but the case
      // never is: a reverse gets the briefing it has to argue from, everything
      // else the screen with its own Briefing on it. Nothing goes straight
      // into a conversation.
      if (!event.skipMicCheck) return { screen: "mic-check", cut: "none" };
      return { screen: event.reverse ? "brief" : "case-brief", cut: "none" };

    case "micConfirmed":
      // A reverse goes to its briefing (F-61) — the same screen the offer
      // under a wrap-up leads to, reached the same way.
      if (context.reverse) return { screen: "brief", cut: "none" };
      // A drawn Scenario is thrown for first; the fade belongs between the
      // throw and the call, not in front of the throw. The two branches cannot
      // both apply: reverses are not in the random Scenario's pool.
      if (context.drawn) {
        return context.reducedMotion
          ? { screen: "incoming", cut: "fade" }
          : { screen: "rolling", cut: "none" };
      }
      // Nothing to read means nothing to stop for. Null is not "nothing": the
      // case may still be in flight, and `caseArrivedEmpty` moves on if it
      // turns out to hold nothing.
      if (hasNothingToRead(context)) return { screen: "incoming", cut: "fade" };
      return { screen: "case-brief", cut: "none" };

    case "caseArrivedEmpty":
    case "caseRead":
    case "rollFinished":
      return { screen: "incoming", cut: "fade" };

    case "callAccepted":
      return { screen: "call", cut: "none" };

    case "callEnded":
      // Straight to the wrap-up's waiting screen where one is being written,
      // and straight past it where none is (ADR 0066).
      return { screen: event.stored ? "analysing" : "transcript", cut: "none" };

    case "analysed":
      return { screen: "transcript", cut: "none" };

    case "micCheckCancelled":
    case "restarted":
      return { screen: "setup", cut: "none" };
  }
}

/** Whether the committed case has arrived and holds nothing worth a screen. */
function hasNothingToRead(context: FlowContext): boolean {
  const c = context.committedCase;
  return c !== null && !c.briefing && !c.facts;
}

/**
 * Whether confirming the mic check leads to a briefing rather than the call.
 * Derived from `nextScreen`, so the button's label and its press cannot disagree
 * (see `MicCheck`); it may flip once while the case is in flight.
 */
export function briefingFollows(context: FlowContext): boolean {
  const { screen } = nextScreen(context, { type: "micConfirmed" });
  return screen === "brief" || screen === "case-brief";
}
