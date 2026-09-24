import type { ScenarioCategory } from "../scenarioLibrary";

/** The kind of call a focus goal is practised in (dashboard concept, 5.E): the
 * first entry of `practised_in` in `backend/db/seed_data.py`, held to it by
 * `tests/test_recommendations.py`. `null` = any unplayed Scenario; a goal absent
 * here gets no suggestion, so a new catalogue goal forces a decision. */
export const PRACTICE_CATEGORY: Record<string, ScenarioCategory | null> = {
  // Phases of a call bind to the kind of call they belong to — where such a
  // kind exists. Every call has an opening, and no category is *about* openings,
  // so that one binds to none: the same reason the voice goals below do not
  // steer. A closing is different: "Abschluss & Einwand" is the kind of call
  // whose whole point is getting to one.
  opening: null,
  needs_analysis: "requirements",
  objection_handling: "closing",
  closing: "closing",
  // Impact: composure is practised where a call goes wrong. Its row names a
  // fault report first and a pricing call second; the first is this one.
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
