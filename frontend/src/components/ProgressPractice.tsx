import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import type { FocusGoal, SessionSummary } from "../protocol";
import { ROUTES, type TrainingStart } from "../routes";
import { listScenarios, type ScenarioCard } from "../scenarioLibrary";
import { mentionSummary } from "../utils/goalMentions";
import { PRACTICE_CATEGORY, PRACTICE_REASON } from "../utils/practiceRoutes";

/**
 * Block E of the dashboard: one thing to practise next.
 *
 * One suggestion and not a list. The decision about what to train next should
 * end in a click, and a stack of options is the same screen again with the
 * decision handed back to the reader.
 *
 * It always names where it comes from. "Weil der Abschluss in drei Ihrer
 * Auswertungen genannt wurde" is what makes this a suggestion; the same button
 * without that sentence is an instruction, and this screen has no standing to
 * give one (ADR 0004, ADR 0065).
 *
 * Three routes, in the order section 5.E of the concept sets out:
 *
 *   1. A follow-up Scenario (F-60) written from the very training where the
 *      point was last named. The best possible hit and no new logic: the case
 *      is the one the point was about.
 *   2. Otherwise a Scenario of the kind the goal is practised in
 *      (`PRACTICE_CATEGORY`, an editorial table), preferring one not played
 *      yet.
 *   3. For goals that bind to no kind of call, any Scenario not played yet,
 *      which widens their practice rather than narrowing it.
 *
 * The partner is the Persona from the training where the point was last named.
 * Not chosen and not varied: keeping the same voice is what makes the next call
 * an exercise on the point rather than a different call altogether. The wire
 * carries no difficulty on a Persona, so "a more demanding partner" is not
 * something this could pick even if it should.
 */
export default function ProgressPractice({
  sessions,
  catalogue,
}: {
  sessions: SessionSummary[];
  catalogue: FocusGoal[];
}) {
  const navigate = useNavigate();
  const [library, setLibrary] = useState<ScenarioCard[] | null>(null);

  const { improvements } = mentionSummary(sessions);
  const target = improvements[0] ?? null;
  const source = target ? lastNaming(sessions, target.goal) : null;
  // The detail of that one training, for its follow-up and its Persona. Called
  // unconditionally with null when there is no candidate, which the hook takes.
  const { detail } = useStoredSession(source?.session_id ?? null);

  useEffect(() => {
    if (!target) return;
    let cancelled = false;
    listScenarios()
      .then((cards) => !cancelled && setLibrary(cards))
      // A failed library leaves route 1 working and the others silent, which is
      // better than an error box on a block that is an offer to begin with.
      .catch(() => !cancelled && setLibrary([]));
    return () => {
      cancelled = true;
    };
  }, [target]);

  if (!target || !source) return null;

  const goal = catalogue.find((entry) => entry.key === target.goal);
  const category = target.goal in PRACTICE_CATEGORY ? PRACTICE_CATEGORY[target.goal] : undefined;
  // Absent from the editorial table: somebody added a goal and did not decide
  // what it is practised in. Silence is the honest answer, not a random call.
  if (category === undefined) return null;

  const personaId = detail?.persona_id ?? null;
  const followUp = detail?.follow_up ?? null;
  const suggestion = followUp
    ? { id: followUp.id, name: followUp.name, why: "aus genau diesem Gespräch entworfen" }
    : pickScenario(library, sessions, category);

  if (!suggestion || !personaId) return null;

  return (
    <section className="progress-section" aria-labelledby="practice-title">
      <div className="progress-section-head">
        <h2 id="practice-title">Was Sie als Nächstes üben könnten</h2>
      </div>

      <div className="card progress-practice">
        {/* The ground, then the offer, then the button. That order is the
            argument: a suggestion whose ground the reader has not seen is an
            instruction, and this screen has no standing to give one. */}
        <p className="progress-practice-why">
          <span className="progress-practice-chip">Vorschlag</span>
          {goal?.title ?? target.goal} wurde in {target.count} Ihrer Auswertungen als
          Verbesserungspunkt genannt, zuletzt am {formatDay(source.started_at)} im Gespräch
          „{source.scenario}“.
        </p>

        <div className="progress-practice-offer">
          <div className="progress-practice-text">
            <p className="progress-practice-what">{suggestion.name}</p>
            <ul className="progress-practice-facts">
              <li>mit {source.persona}</li>
              <li>{suggestion.why}</li>
            </ul>
          </div>

          <button
            type="button"
            // `consent-button` is the app's primary button, misnamed after the
            // screen it first stood on. The `button-primary` that used to be
            // here is styled nowhere, so this rendered as a bare browser
            // button.
            className="consent-button consent-button-primary progress-practice-start"
            onClick={() => {
              // The same door the history uses to start a follow-up: the two
              // screens are separate routes, so the pairing travels as location
              // state and the training screen consumes it once (see
              // `TrainingStart`).
              const start: TrainingStart = { scenarioId: suggestion.id, personaId };
              navigate(ROUTES.training, { state: { start } });
            }}
          >
            Dieses Training starten
          </button>
        </div>

        <p className="progress-practice-note">
          Ein Vorschlag, keine Vorgabe. Er folgt daraus, was Ihre Auswertungen mehrfach genannt
          haben, und aus einer festen Zuordnung, welches Ziel sich in welcher Art von Gespräch
          üben lässt. Über die Startseite können Sie jederzeit etwas anderes wählen.
        </p>
      </div>
    </section>
  );
}

/** The most recent training whose wrap-up named this goal as an improvement.
 *  The listing is newest first, so the first match is the latest. */
function lastNaming(sessions: SessionSummary[], goal: string): SessionSummary | null {
  return (
    sessions.find((session) =>
      session.feedback_goals.some((tag) => tag.kind === "improvement" && tag.goal === goal),
    ) ?? null
  );
}

/**
 * A Scenario of the right kind, preferring one the user has not played.
 *
 * Unplayed first because repeating the same case tests recall as much as
 * delivery, and because it widens their practice at no cost. Where everything
 * of that kind has been played, the least recently played one is still a
 * better answer than none.
 *
 * Matched on the title, which is what both the history row and the library card
 * carry. An id on the history row would be sturdier; the title is what is on
 * the wire today and a duplicate title would only cost this block a slightly
 * worse suggestion.
 */
function pickScenario(
  library: ScenarioCard[] | null,
  sessions: SessionSummary[],
  category: string | null,
): { id: string; name: string; why: string } | null {
  if (!library || library.length === 0) return null;

  const played = new Set(sessions.map((session) => session.scenario));
  // Reverses are excluded: one replays a specific call and cannot be handed out
  // as general practice (ADR 0070).
  const usable = library.filter((card) => !card.reverse);
  const ofKind = category ? usable.filter((card) => card.category === category) : usable;
  const pool = ofKind.length > 0 ? ofKind : usable;

  const fresh = pool.filter((card) => !played.has(card.name));
  const chosen = fresh[0] ?? pool[0];
  if (!chosen) return null;

  const why = category
    ? `eines der ${PRACTICE_REASON[category] ?? "passenden Gespräche"}`
    : "ein Gespräch, das Sie noch nicht geführt haben";
  return { id: chosen.id, name: chosen.name, why };
}

/** The day a training happened, for the sentence that says where the
 *  suggestion comes from. */
function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "long",
  });
}
