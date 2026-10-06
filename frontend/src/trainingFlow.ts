/** The training flow's screens and transitions as one pure table: where a press
 * leads and how it is covered. Side effects stay in App.tsx. */

export type Screen =
  | "setup"
  | "mic-check"
  /** Between the check and the phone; a reverse's equivalent is "brief". */
  | "case-brief"
  | "brief"
  | "rolling"
  | "incoming"
  | "call"
  /** Skipped for an unstored Session, which has no wrap-up coming (ADR 0066). */
  | "analysing"
  | "transcript";

/** Performed by `components/ScreenTransition.tsx`. */
export type Cut = "none" | "fade";

/** A fact only one handler knows rides on its event instead, so forgetting it fails to compile. */
export interface FlowContext {
  /** ADR 0070: to its own briefing, not the phone. */
  reverse: boolean;
  /** F-62: thrown for, its case not read beforehand. */
  drawn: boolean;
  /** Null while in flight routes to the briefing: an empty case moves on by itself, a skipped one cannot be undone. */
  committedCase: { briefing: string | null; facts: string | null } | null;
  /** The throw is skipped, not shown still. */
  reducedMotion: boolean;
}

export type FlowEvent =
  /** `skipMicCheck` straight from a finished training (F-60/F-61). */
  | { type: "sessionCommitted"; reverse: boolean; skipMicCheck: boolean }
  | { type: "micConfirmed" }
  /** Only for a way in that commits before its case is fetched. */
  | { type: "caseArrivedEmpty" }
  | { type: "caseRead" }
  | { type: "rollFinished" }
  /** The only event that reaches the call, so App's entry steps cannot be bypassed. */
  | { type: "callAccepted" }
  /** `stored`: a wrap-up is coming. */
  | { type: "callEnded"; stored: boolean }
  | { type: "analysed" }
  | { type: "micCheckCancelled" }
  | { type: "restarted" };

export interface Transition {
  screen: Screen;
  cut: Cut;
}

/** Exhaustive, so a new event fails to compile until its destination is decided. */
export function nextScreen(context: FlowContext, event: FlowEvent): Transition {
  switch (event.type) {
    case "sessionCommitted":
      // The check is skipped after a training; the case never is.
      if (!event.skipMicCheck) return { screen: "mic-check", cut: "none" };
      return { screen: event.reverse ? "brief" : "case-brief", cut: "none" };

    case "micConfirmed":
      if (context.reverse) return { screen: "brief", cut: "none" };
      // Thrown for first; reverses are never drawn.
      if (context.drawn) {
        return context.reducedMotion
          ? { screen: "incoming", cut: "fade" }
          : { screen: "rolling", cut: "none" };
      }
      // Null may still be in flight; `caseArrivedEmpty` moves on.
      if (hasNothingToRead(context)) return { screen: "incoming", cut: "fade" };
      return { screen: "case-brief", cut: "none" };

    case "caseArrivedEmpty":
    case "caseRead":
    case "rollFinished":
      return { screen: "incoming", cut: "fade" };

    case "callAccepted":
      return { screen: "call", cut: "none" };

    case "callEnded":
      return { screen: event.stored ? "analysing" : "transcript", cut: "none" };

    case "analysed":
      return { screen: "transcript", cut: "none" };

    case "micCheckCancelled":
    case "restarted":
      return { screen: "setup", cut: "none" };
  }
}

function hasNothingToRead(context: FlowContext): boolean {
  const c = context.committedCase;
  return c !== null && !c.briefing && !c.facts;
}

/** Derived from `nextScreen`, so the button's label and press agree. */
export function briefingFollows(context: FlowContext): boolean {
  const { screen } = nextScreen(context, { type: "micConfirmed" });
  return screen === "brief" || screen === "case-brief";
}
