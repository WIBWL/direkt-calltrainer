import type { ScenarioCategory } from "../scenarioLibrary";

/**
 * Which kind of call a focus goal is practised in.
 *
 * Editorial, not computed. Nothing in the data says objection handling is best
 * practised on a pricing call — that is a judgement about the subject matter,
 * written down here so it can be argued with rather than buried in a model
 * call (dashboard concept, section 5.E).
 *
 * `null` means the goal binds to no kind of call: speaking rate or articulation
 * can be worked on in any conversation, so the suggestion is simply an unplayed
 * Scenario, which widens their practice rather than narrowing it.
 *
 * A goal absent from this table gets no suggestion — deliberate rather than a
 * default, so adding a catalogue goal forces somebody to decide what it is
 * practised in instead of quietly inheriting "any scenario".
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
