import type {
  FeedbackPoint,
  Measurement,
  SessionDetail,
  SessionTurn,
} from "../protocol";
import { formatOffset } from "../utils/time";
import { useSessionFeedback } from "../hooks/useSessionFeedback";
import Sparkline from "./Sparkline";

/** What a screen can do with the follow-up Scenario (F-60): open it in the
 * editor, or start it as the next call. Both belong to whoever owns the screen,
 * so they are passed in — the post-call screen starts the call itself, the
 * history hands the pairing to the training flow.
 *
 * `onStart` gets the Persona too: the follow-up is played against the same
 * partner as the training it came out of, so there is nothing left to choose. */
export interface FollowUpActions {
  onEdit: (scenarioId: string) => void;
  onStart: (scenarioId: string, personaId: string) => void;
}

/** How many decimals a metric reads naturally in. Counts are whole things;
 * seconds and percentages are not. */
const DECIMALS: Record<string, number> = { questions: 0, word_count: 0, pace: 0, talk_share: 0 };

/** Everything that is not a finished wrap-up is a one-line notice. There is
 * no entry for "ready": the hook reports it only once feedback is present. */
const NOTICE: Record<string, string> = {
  loading: "Das Feedback wird erstellt – einen Moment bitte.",
  missing: "Für dieses Gespräch wurde kein Feedback gespeichert.",
  failed:
    "Das Feedback konnte nicht erstellt werden. Das Gesprächsprotokoll unten ist davon nicht betroffen.",
};

/**
 * The post-call wrap-up (F-09/F-10/F-53): the narrative the model wrote, and
 * the statistics it was written from.
 *
 * The two are shown together deliberately. ADR 0004 makes the qualitative text
 * the feedback itself, and ADR 0049 keeps every number out of the model's
 * hands — so the figures here are the evidence behind the text, never a score.
 * Each one describes the whole call rather than a single utterance (ADR 0051).
 *
 * The phase block (F-42) sits below the figures on purpose: it is the one part
 * of the wrap-up that is about a change over the call rather than about a
 * moment or a total, so it reads as a closing observation rather than as
 * another statistic.
 *
 * Owns the polling itself, so it is only running while this screen is mounted.
 */
export default function FeedbackView({
  sessionId,
  followUp,
}: {
  sessionId: string | null;
  /** Omitted where there is nowhere to act on the follow-up (F-60). */
  followUp?: FollowUpActions;
}) {
  const { detail, state } = useSessionFeedback(sessionId);

  if (!detail?.feedback) {
    return (
      <div className="card">
        <p className="muted">{NOTICE[state]}</p>
      </div>
    );
  }
  // The hook keeps polling past the wrap-up while the follow-up is still being
  // written, so "loading" here is what that block waits on.
  return (
    <FeedbackReport
      detail={detail}
      followUp={followUp && { ...followUp, pending: state === "loading" }}
    />
  );
}

/**
 * The wrap-up itself, given data that has already been fetched.
 *
 * Split from the component above so a screen that already holds a
 * `SessionDetail` — the history's detail page, which needs the Transcript from
 * the same response — can render the report without asking for it again.
 *
 * Renders nothing when the Session carries no wrap-up. What to say instead is
 * the caller's to decide, because the honest sentence differs: on the post-call
 * screen one is still being generated, in the history none ever was.
 *
 * The follow-up offer (F-60) stays a prop for the same reason: both screens
 * that show it can open the editor and start a training, but they do it
 * differently — after a call the flow is already here, from the history it has
 * to be handed over — and only one of them has a wrap-up still on its way to
 * wait for.
 */
export function FeedbackReport({
  detail,
  followUp,
}: {
  detail: SessionDetail;
  followUp?: (FollowUpActions & { pending: boolean }) | undefined;
}) {
  const { feedback, measurements, turns, persona, scenario } = detail;
  if (!feedback) return null;

  const improvements = feedback.points.filter((p) => p.kind === "improvement");

  return (
    <>
      <div className="feedback-meta" aria-label="Trainingsdetails">
        <span>{scenario}</span>
        <span className="feedback-meta-separator" aria-hidden="true">
          ·
        </span>
        <span>{persona}</span>
      </div>

      <div className="card feedback-summary-card">
        <div className="feedback-summary-kicker">QUALITATIVE EINORDNUNG</div>
        <h2 className="feedback-summary-title">Zusammenfassung</h2>
        <p className="feedback-summary-text">{feedback.summary}</p>
      </div>

      <div className="feedback-details">
        <PointList
          eyebrow="STÄRKEN"
          title="Das gelang gut"
          points={feedback.points.filter((p) => p.kind === "strength")}
          turns={turns}
          tone="success"
        />

        <PointList
          eyebrow="WEITERENTWICKELN"
          title="Das können Sie verbessern"
          points={improvements}
          turns={turns}
          tone="danger"
        />
      </div>

      {followUp && improvements.length > 0 && (
        <FollowUp scenario={detail.follow_up} personaId={detail.persona_id} {...followUp} />
      )}

      {feedback.phase_language && (
        <section className="feedback-phase-card">
          <div className="feedback-phase-eyebrow">GESPRÄCHSFÜHRUNG</div>
          <h2 className="feedback-phase-title">Phasengerechte Sprache</h2>

          <p className="feedback-phase-text">{feedback.phase_language}</p>

          <p className="feedback-phase-note">
            Betrachtet wird, ob sich die Gesprächsführung passend zwischen Einstieg,
            Anliegen und Abschluss verändert.
          </p>
        </section>
      )}

      <MetricSection measurements={measurements} />
    </>
  );
}

/**
 * The call's statistics (F-53), which exist independently of the narrative:
 * they are computed while the call runs (ADR 0047/0048) and stored with the
 * Session, so a Session whose wrap-up never got generated still has them.
 *
 * Never a judgement, only a reading — ADR 0051 declined to invent the norms
 * that would be needed to say whether a figure is good, and the note under the
 * grid says so rather than leaving the user to assume a direction.
 */
export function MetricSection({ measurements }: { measurements: Measurement[] }) {
  if (measurements.length === 0) return null;

  return (
    <section className="feedback-metrics-section">
      <div className="feedback-metrics-eyebrow">ERGÄNZENDE AUSWERTUNG</div>
      <h2 className="feedback-metrics-title">Kennzahlen zum Gespräch</h2>

      <div className="metric-grid">
        {measurements.map((measurement) => (
          <Metric key={measurement.key} measurement={measurement} />
        ))}
      </div>

      <p className="metric-disclaimer">
        Reine Messwerte, ohne Zielbereich: für diese Nutzergruppe gibt es keinen
        belegten Normwert, an dem sie zu messen wären.
      </p>
    </section>
  );
}

/** The next exercise, built from the points above (F-60). Nobody asks for it:
 * the worker writes it with the wrap-up and stores it as an ordinary Scenario
 * of the User's (ADR 0069), so this offers a row that already exists rather
 * than a draft. It arrives a little after the wrap-up, hence the busy line.
 *
 * "Starten" goes straight into the call, against the Persona this training was
 * played with: the exercise follows from that conversation, so re-picking a
 * partner would be a step with only one sensible answer. The Scenario stays an
 * ordinary row in the library, so a different partner is a matter of starting
 * it from the setup screen instead. */
function FollowUp({
  scenario,
  personaId,
  pending,
  onEdit,
  onStart,
}: {
  scenario: SessionDetail["follow_up"];
  personaId: string;
  pending: boolean;
} & FollowUpActions) {
  if (!scenario) {
    if (!pending) return null;
    return (
      <div className="card follow-up">
        <p className="follow-up-note">
          Aus diesen Punkten wird gerade ein Folgeszenario gebaut – das dauert einen
          Moment.
        </p>
      </div>
    );
  }

  return (
    <div className="card follow-up">
      <p>
        Daraus ist Ihr nächstes Gespräch entstanden: eine neue Situation im selben
        Umfeld, die genau das verlangt, was hier gefehlt hat. Es liegt unter
        „Folgeszenario“ in Ihrer Auswahl.
      </p>
      <p className="follow-up-name">{scenario.name}</p>
      <p className="follow-up-teaser">{scenario.short_description}</p>
      <div className="follow-up-actions">
        <button
          type="button"
          className="follow-up-button"
          onClick={() => onStart(scenario.id, personaId)}
        >
          Starten
        </button>
        <button type="button" className="follow-up-draft" onClick={() => onEdit(scenario.id)}>
          Bearbeiten
        </button>
      </div>
      <p className="follow-up-note">
        „Starten“ beginnt das Gespräch direkt – mit demselben Gesprächspartner wie in
        diesem Training.
      </p>
    </div>
  );
}


function PointList({
  eyebrow,
  title,
  points,
  turns,
  tone,
}: {
  eyebrow: string;
  title: string;
  points: FeedbackPoint[];
  turns: SessionTurn[];
  tone: "success" | "danger";
}) {
  if (points.length === 0) return null;
  return (
    <section className={`feedback-point-card ${tone}`}>
      <div className="feedback-point-header">
        <div className="feedback-point-icon" aria-hidden="true">
          {tone === "success" ? "✓" : "!"}
        </div>

        <div>
          <div className="feedback-point-eyebrow">{eyebrow}</div>
          <h2 className="feedback-point-title">{title}</h2>
        </div>
      </div>

      <div className="feedback-point-list">
        {points.map((point, i) => {
          const turn =
            point.turn_id !== null
              ? turns.find((candidate) => candidate.turn_id === point.turn_id)
              : undefined;

          return (
            <div className="feedback-point-item" key={i}>
              {turn && (
                <span className="feedback-point-time">
                  {formatOffset(turn.start_offset_ms)}
                </span>
              )}
              <p>{point.text}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ measurement }: { measurement: Measurement }) {
  // The one metric with a course rather than a single number: loudness across
  // the whole call, as Praat measured it at a fixed rate (ADR 0047/0051).
  const curve = measurement.detail?.curve_db as (number | null)[] | undefined;
  const decimals = DECIMALS[measurement.key] ?? 1;
  return (
    <div className={`metric${measurement.key === "loudness" ? " metric-loudness" : ""}`}>
      <span className="metric-name">{measurement.name}</span>
      <span className="metric-value">
        {measurement.value.toFixed(decimals)}
        {measurement.unit && measurement.unit !== "Anzahl"
          ? ` ${measurement.unit}`
          : ""}
      </span>
      {curve && <Sparkline values={curve} label={`${measurement.name} im Gesprächsverlauf`} />}
    </div>
  );
}
