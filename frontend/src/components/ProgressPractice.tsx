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

/** Block E: one thing to practise next, always naming its ground (ADR 0004/0065).
 * The follow-up (F-60) of the training that last named it, else a Scenario of the
 * goal's kind, else any unplayed one; the Persona from that training. */
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
  // Null without a candidate, which the hook takes.
  const { detail } = useStoredSession(source?.session_id ?? null);

  // A boolean: `mentionSummary` rebuilds the target every render, which would loop the fetch.
  const hasTarget = target !== null;
  useEffect(() => {
    if (!hasTarget) return;
    let cancelled = false;
    listScenarios()
      .then((cards) => !cancelled && setLibrary(cards))
      // An offer fails silently rather than with an error box.
      .catch(() => !cancelled && setLibrary([]));
    return () => {
      cancelled = true;
    };
  }, [hasTarget]);

  if (!target || !source) return null;

  const goal = catalogue.find((entry) => entry.key === target.goal);
  const category = target.goal in PRACTICE_CATEGORY ? PRACTICE_CATEGORY[target.goal] : undefined;
  // A goal nobody mapped to a call type: silence, not a random call.
  if (category === undefined) return null;

  const since = wordSince(sessions, target.goal, source);
  const personaId = detail?.persona_id ?? null;
  const followUp = detail?.follow_up ?? null;
  const suggestion = followUp
    ? { id: followUp.id, name: followUp.name, why: "aus genau diesem Gespräch entworfen" }
    : pickScenario(library, sessions, category);

  if (!suggestion || !personaId) return null;

  return (
    <section className="card" aria-labelledby="practice-title">
      <h3 className="recurring-heading" id="practice-title">
        Als Nächstes üben
      </h3>

      {/* Ground before offer: an unexplained suggestion is an instruction. */}
      <div className="progress-practice-band">
        <p className="progress-practice-why">
          <span className="progress-practice-chip">Vorschlag</span>
          {goal?.title ?? target.goal} wurde in {target.count} Ihrer Auswertungen als
          Verbesserungspunkt genannt, zuletzt am{" "}
          {formatDayMonth(source.started_at) ?? source.started_at} im Gespräch
          „{source.scenario}“.
        </p>

        {since && (
          // Never claims causation (ADR 0080).
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
            // `consent-button` is the app's primary button, misnamed.
            className="consent-button consent-button-primary progress-practice-start"
            onClick={() => {
              // Handed over as location state (`TrainingStart`).
              const start: TrainingStart = { scenarioId: suggestion.id, personaId };
              navigate(ROUTES.training, { state: { start } });
            }}
          >
            Dieses Training starten
          </button>
        </div>
      </div>

      {/* "A suggestion, not an instruction" stays in view; the method sits behind the "i". */}
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

/** The listing is newest first, so the first match is the latest. */
function lastNaming(sessions: SessionSummary[], goal: string): SessionSummary | null {
  return (
    sessions.find((session) =>
      session.feedback_goals.some((tag) => tag.kind === "improvement" && tag.goal === goal),
    ) ?? null
  );
}

/** Derived, never stored: a stored press would be training data (ADR 0066). */
function wordSince(
  sessions: SessionSummary[],
  goal: string,
  source: SessionSummary,
): GoalStatement | null {
  const newest = statementsFor(sessions, [goal])[0];
  if (!newest || newest.sessionId === source.session_id) return null;
  return newest;
}

/** Unplayed first, else least recently. Matched on title, which both row and card carry. */
function pickScenario(
  library: ScenarioCard[] | null,
  sessions: SessionSummary[],
  category: string | null,
): { id: string; name: string; why: string } | null {
  if (!library || library.length === 0) return null;

  const played = new Set(sessions.map((session) => session.scenario));
  // A reverse replays one specific call (ADR 0070).
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
