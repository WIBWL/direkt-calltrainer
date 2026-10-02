import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import type { FocusGoal, SessionSummary } from "../protocol";
import { ROUTES, type TrainingStart } from "../routes";
import { listScenarios, type ScenarioCard } from "../scenarioLibrary";
import { mentionSummary, statementsFor, type GoalStatement } from "../utils/goalMentions";
import { PRACTICE_CATEGORY, PRACTICE_REASON } from "../utils/practiceRoutes";
import { formatDayMonth } from "../utils/time";
import InfoDetails from "./InfoDetails";

/**
 * Block E: one thing to practise next, always naming its ground, else it is an instruction (ADR 0004, ADR 0065).
 * Routes (concept 5.E): the follow-up (F-60) from the training that last named it, else a Scenario of the goal's
 * kind (`PRACTICE_CATEGORY`, unplayed first), else any unplayed one. Persona held constant from that training.
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

  // Keyed on whether there is a target rather than on the target object, which
  // `mentionSummary` rebuilds on every render: as a dependency it would re-run
  // this after every response and fetch the library in a loop. Which goal it is
  // does not change what is fetched.
  const hasTarget = target !== null;
  useEffect(() => {
    if (!hasTarget) return;
    let cancelled = false;
    listScenarios()
      .then((cards) => !cancelled && setLibrary(cards))
      // A failed library leaves route 1 working and the others silent, which is
      // better than an error box on a block that is an offer to begin with.
      .catch(() => !cancelled && setLibrary([]));
    return () => {
      cancelled = true;
    };
  }, [hasTarget]);

  if (!target || !source) return null;

  const goal = catalogue.find((entry) => entry.key === target.goal);
  const category = target.goal in PRACTICE_CATEGORY ? PRACTICE_CATEGORY[target.goal] : undefined;
  // Absent from the editorial table: somebody added a goal and did not decide
  // what it is practised in. Silence is the honest answer, not a random call.
  if (category === undefined) return null;

  const since = wordSince(sessions, target.goal, source);
  const personaId = detail?.persona_id ?? null;
  const followUp = detail?.follow_up ?? null;
  const suggestion = followUp
    ? { id: followUp.id, name: followUp.name, why: "aus genau diesem Gespräch entworfen" }
    : pickScenario(library, sessions, category);

  if (!suggestion || !personaId) return null;

  // A band under the recurring block's two lists rather than a section of its
  // own (see `ProgressRecurring`), headed the way those lists are.
  return (
    <section className="card" aria-labelledby="practice-title">
      <h3 className="recurring-heading" id="practice-title">
        Als Nächstes üben
      </h3>

      {/* Ground, then offer, then button, in one column: a suggestion whose ground the reader has not seen
          is an instruction. */}
      <div className="progress-practice-band">
        <p className="progress-practice-why">
          <span className="progress-practice-chip">Vorschlag</span>
          {goal?.title ?? target.goal} wurde in {target.count} Ihrer Auswertungen als
          Verbesserungspunkt genannt, zuletzt am{" "}
          {formatDayMonth(source.started_at) ?? source.started_at} im Gespräch
          „{source.scenario}“.
        </p>

        {since && (
          // Looks back (Zimmerman's cycle): the wrap-ups raised this, and afterwards a wrap-up said this.
          // Causation is never claimed — that would be the measurement ADR 0080 refuses.
          <p className="progress-practice-since">
            <span className="progress-practice-chip">Seither</span>
            In Ihrem Training am {formatDayMonth(since.at) ?? since.at} („{since.scenario}“)
            stand dazu{" "}
            {since.kind === "strength" ? "als Stärke" : "als Verbesserungspunkt"}:{" "}
            <q>{since.text}</q>
          </p>
        )}

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
      </div>

      {/* The line calling this a suggestion and not an instruction stays in
          view: it is what keeps the button above from reading as an order. How
          the suggestion was put together is background and sits behind the "i",
          on the same line — two trailing rows each with their own weight made
          the foot of the block heavier than the offer in it. */}
      <div className="progress-practice-foot">
        <p className="progress-practice-note">
          Ein Vorschlag, keine Vorgabe. Über die Startseite können Sie jederzeit etwas anderes
          wählen.
        </p>
        <InfoDetails label="Wie dieser Vorschlag zustande kommt">
          <p>
            Er folgt daraus, was Ihre Auswertungen mehrfach als Verbesserung genannt haben. Gibt
            es zu dem Gespräch, in dem das zuletzt vorkam, ein Folgeszenario, wird dieses
            vorgeschlagen. Sonst ein Szenario aus der Art von Gespräch, in der sich das Ziel
            üben lässt, bevorzugt eines, das Sie noch nicht gespielt haben.
          </p>
          <p>
            Der Gesprächspartner ist derselbe wie in dem Training, in dem der Punkt zuletzt
            genannt wurde. So bleibt die Stimme gleich, und das nächste Gespräch ist eine Übung
            an genau diesem Punkt.
          </p>
        </InfoDetails>
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
 * What a wrap-up has said about this goal since the suggestion's training, or null. Derived, never stored (a
 * stored press would be per-device or training data, ADR 0066). `source` is the newest training naming the goal,
 * so a newest statement from a later training is the case worth showing.
 */
function wordSince(
  sessions: SessionSummary[],
  goal: string,
  source: SessionSummary,
): GoalStatement | null {
  const newest = statementsFor(sessions, [goal])[0];
  if (!newest || newest.sessionId === source.session_id) return null;
  return newest;
}

/**
 * A Scenario of the right kind, unplayed first (else the least recently played). Matched on the title, the one
 * thing both the history row and the library card carry; a duplicate title only costs a worse suggestion.
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
