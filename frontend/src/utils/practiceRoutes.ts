import type { ScenarioCategory } from "../scenarioLibrary";

/**
 * Which kind of call a focus goal is practised in.
 *
 * Editorial, not computed. There is nothing in the data that says objection
 * handling is best practised on a pricing call; that is a judgement about the
 * subject matter, and it is written down here so it can be argued with rather
 * than buried in a model call. Section 5.E of the dashboard concept sets it
 * out, and this is that table.
 *
 * `null` means the goal does not bind to a kind of call at all. Speaking rate
 * or articulation can be worked on in any conversation, so the suggestion is
 * simply a Scenario the user has not played yet, which also widens their
 * practice (F-62's Trainingsvielfalt) instead of narrowing it.
 *
 * A goal absent from this table gets no suggestion. That is deliberate rather
 * than a default: adding a goal to the catalogue should force somebody to
 * decide what it is practised in, not quietly inherit "any scenario".
 */
export const PRACTICE_CATEGORY: Record<string, ScenarioCategory | null> = {
  // Phases of a call bind to the kind of call they belong to.
  opening: "operations",
  needs_analysis: "requirements",
  objection_handling: "pricing",
  closing: "closing",
  // Impact: composure is practised where a call goes wrong, and a fault report
  // is where a caller arrives annoyed.
  composure: "operations",
  empathy: "operations",
  active_listening: "requirements",
  // Paraverbal, plus the two that are about how much is said rather than about
  // the matter: any call will do.
  pace: null,
  intonation: null,
  articulation: null,
  conciseness: null,
  talk_share: null,
};

/** Why this Scenario, in one clause, for the sentence that names the reason.
 *  A suggestion without one is an instruction. */
export const PRACTICE_REASON: Record<string, string> = {
  operations: "Störungs- und Betriebsgespräche",
  requirements: "Beratungsgespräche",
  pricing: "Preisgespräche",
  closing: "Abschlussgespräche",
};
