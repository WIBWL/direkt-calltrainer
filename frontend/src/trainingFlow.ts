/**
 * Where a press leads: the training flow's screens and the transitions between
 * them, as one table, so the machine can be read in one place instead of by
 * finding every call site.
 *
 * Pure on purpose: no React, no network, no environment. Everything a
 * transition depends on is passed in, which is what makes the table testable
 * without a WebSocket, an AudioContext or a 15 MB ONNX download — none of which
 * the decisions here have anything to do with.
 *
 * It decides *where* and *how covered*, never *what else happens*. Activating
 * playback, sending `session.activate` and unmuting the microphone stay in
 * `App.tsx`, which performs them on the one event that reaches the call.
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
export type Cut = "none" | "fade" | "reverse";

/**
 * Everything the flow routes on, gathered from the caller.
 *
 * Passed in rather than read here — `prefersReducedMotion()` in particular is
 * an environment query, and a function that makes one cannot be tested by
 * describing a situation.
 */
export interface FlowContext {
  /** The committed Scenario replays a finished Session with the roles swapped
   * (ADR 0070), so it goes to its own briefing rather than to the phone. */
  reverse: boolean;
  /** A random Scenario was drawn (F-62): it is thrown for, and its case is
   * deliberately not read beforehand. */
  drawn: boolean;
  /**
   * The committed case as the detail route serves it, or null while that
   * request is in flight.
   *
   * Null routes to the briefing screen, which is the safe answer: a case that
   * turns out to hold nothing moves on by itself a moment later
   * (`caseArrivedEmpty`), whereas skipping a case that turns out to hold
   * something cannot be undone.
   */
  committedCase: { briefing: string | null; facts: string | null } | null;
  /** Whether the User asked for reduced motion. The die has nothing to say
   * standing still, so under it the throw is skipped rather than shown. */
  reducedMotion: boolean;
  /** Whether the microphone check is skipped — true coming straight from a
   * finished training (F-60/F-61), where the microphone was in use seconds ago
   * and its device is still selected. */
  skipMicCheck: boolean;
  /** Whether the finished call was stored, and so has a wrap-up coming. */
  stored: boolean;
}

/** What happened, as the flow hears it. */
export type FlowEvent =
  /** A pairing was committed to and the Session is connecting (ADR 0042). */
  | "sessionCommitted"
  /** The microphone check was confirmed. */
  | "micConfirmed"
  /** The case arrived and holds nothing to read, on a screen already showing
   * it. Only reachable for a way in that commits before its case is fetched. */
  | "caseArrivedEmpty"
  /** The User read the case and pressed on. */
  | "caseRead"
  /** The die finished rolling. */
  | "rollFinished"
  /**
   * The call was accepted — the ringing phone answered, or the reverse's
   * briefing read and its button pressed. A reverse has no phone to answer:
   * there the User is the caller (`_casting` in `session/prompting.py`), so
   * that screen goes straight to the call.
   *
   * The only event that reaches the call, which is what keeps the three things
   * `App` does on the way in from being reachable any other way.
   */
  | "callAccepted"
  /** The call ended, by hang-up, error or the Persona saying goodbye. */
  | "callEnded"
  /** The wrap-up settled, or the User would rather not wait for it. */
  | "analysed"
  /** The microphone check was abandoned, dropping the committed Session. */
  | "micCheckCancelled"
  /** Back to the beginning from the end of a training. */
  | "restarted";

export interface Transition {
  screen: Screen;
  cut: Cut;
}

/**
 * Where an event leads, and what covers the change.
 *
 * The switch is exhaustive on purpose: a new event refuses to compile until
 * someone decides where it goes and whether a cut covers it, which is exactly
 * what is easy to forget.
 */
export function nextScreen(context: FlowContext, event: FlowEvent): Transition {
  switch (event) {
    case "sessionCommitted":
      // The check is skipped coming out of a finished training, but the case
      // never is: a reverse gets the briefing it has to argue from, everything
      // else the screen with its own Briefing on it. Nothing goes straight
      // into a conversation.
      if (!context.skipMicCheck) return { screen: "mic-check", cut: "none" };
      return { screen: context.reverse ? "brief" : "case-brief", cut: "none" };

    case "micConfirmed":
      // A reverse goes to its briefing behind the card turn (F-61) — the same
      // screen the offer under a wrap-up leads to, reached the same way.
      if (context.reverse) return { screen: "brief", cut: "reverse" };
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
      return { screen: context.stored ? "analysing" : "transcript", cut: "none" };

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
 * Whether confirming the microphone check leads to a briefing rather than to
 * the call.
 *
 * Asked by the check's button, so its label names the step it actually takes.
 * Derived from `nextScreen` rather than worked out a second time: the two used
 * to be separate expressions reading *different* sources — the router took the
 * briefing from the committed case, the label from the library card — so a
 * Scenario carrying facts but no card briefing promised a call and delivered a
 * page of text, which `MicCheck`'s own docstring names as the thing that must
 * not happen.
 *
 * The label may now flip once, early, while the case is still in flight. That
 * is the honest trade: it is never wrong, where before it never flipped and
 * was sometimes wrong.
 */
export function briefingFollows(context: FlowContext): boolean {
  const { screen } = nextScreen(context, "micConfirmed");
  return screen === "brief" || screen === "case-brief";
}
