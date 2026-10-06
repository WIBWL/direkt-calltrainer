import type { ScenarioCategory } from "../scenarioLibrary";

/** The first `practised_in` entry in `shared/db/seed_data.py` (pinned by test_recommendations.py).
 * `null` = any unplayed Scenario; an absent goal gets no suggestion. */
export const PRACTICE_CATEGORY: Record<string, ScenarioCategory | null> = {
  // Every call has an opening, so it binds to none; a closing is what "Abschluss & Einwand" is about.
  opening: null,
  needs_analysis: "requirements",
  objection_handling: "closing",
  closing: "closing",
  // Practised where a call goes wrong.
  composure: "operations",
  empathy: "operations",
  active_listening: "requirements",
  // Any call will do.
  pace: null,
  intonation: null,
  conciseness: null,
  talk_share: null,
};

/** A suggestion without a reason is an instruction. */
export const PRACTICE_REASON: Record<string, string> = {
  operations: "Störungs- und Betriebsgespräche",
  requirements: "Beratungsgespräche",
  pricing: "Preisgespräche",
  closing: "Abschlussgespräche",
};
