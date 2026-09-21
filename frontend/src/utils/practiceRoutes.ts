import type { ScenarioCategory } from "../scenarioLibrary";

/**
 * Which kind of call a focus goal is practised in.
 *
 * Editorial, not computed — a judgement about the subject matter, written down
 * here so it can be argued with rather than buried in a model call (dashboard
 * concept, section 5.E).
 *
 * The judgement itself is written on each goal's row in the catalogue
 * (`practised_in` in `backend/db/seed_data.py`), where a goal may name several
 * kinds of call — the library suggests all of them. This table is the first of
 * each, the one the single practice suggestion uses, and
 * `tests/test_recommendations.py` holds it to the row: the two had drifted, and
 * a User who picked Einwandbehandlung was sent to a closing call on the setup
 * screen and to a pricing call here.
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
