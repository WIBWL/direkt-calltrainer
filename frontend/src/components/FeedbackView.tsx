import type { FeedbackPoint, Measurement, SessionTurn } from "../protocol";
import { formatOffset } from "../utils/time";
import { useSessionFeedback } from "../hooks/useSessionFeedback";
import Sparkline from "./Sparkline";

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
export default function FeedbackView({ sessionId }: { sessionId: string | null }) {
  const { detail, state } = useSessionFeedback(sessionId);

  if (!detail?.feedback) {
    return (
      <div className="card">
        <p className="muted">{NOTICE[state]}</p>
      </div>
    );
  }

  const { feedback, measurements, turns } = detail;

  return (
    <>
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
          points={feedback.points.filter((p) => p.kind === "improvement")}
          turns={turns}
          tone="danger"
        />
      </div>

      <div className="feedback-next-focus">
        <div className="feedback-next-focus-number">01</div>

        <div className="feedback-next-focus-content">
          <div className="feedback-next-focus-eyebrow">NÄCHSTER TRAININGSFOKUS</div>
          <h2 className="feedback-next-focus-title">Coming Soon</h2>
        </div>
      </div>

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

      {measurements.length > 0 && (
        <section className="feedback-metrics-section">
          <div className="feedback-metrics-eyebrow">ERGÄNZENDE AUSWERTUNG</div>
          <h2 className="feedback-metrics-title">Kennzahlen zum Gespräch</h2>

          <div className="metric-grid">
            {measurements.map((measurement) => (
              <Metric key={measurement.key} measurement={measurement} />
            ))}
          </div>

          <p className="metric-disclaimer">
            Die Kennzahlen dienen als ergänzende Orientierung und werden nicht automatisch bewertet.
          </p>
        </section>
      )}
    </>
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
