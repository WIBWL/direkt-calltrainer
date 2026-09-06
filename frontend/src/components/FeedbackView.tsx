import type { FeedbackPoint, Measurement } from "../protocol";
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

  const { feedback, measurements } = detail;

  return (
    <>
      <div className="card">
        <p>{feedback.summary}</p>
      </div>

      <PointList
        title="Das lief gut"
        points={feedback.points.filter((p) => p.kind === "strength")}
        tone="success"
      />
      <PointList
        title="Daran können Sie arbeiten"
        points={feedback.points.filter((p) => p.kind === "improvement")}
        tone="danger"
      />

      {measurements.length > 0 && (
        <>
          <h2>Zahlen zum Gespräch</h2>
          <div className="card">
            <div className="metric-grid">
              {measurements.map((m) => (
                <Metric key={m.key} measurement={m} />
              ))}
            </div>
            <p className="metric-disclaimer">
              Reine Messwerte, ohne Zielbereich: für diese Nutzergruppe gibt es keinen
              belegten Normwert, an dem sie zu messen wären.
            </p>
          </div>
        </>
      )}

      {feedback.phase_language && (
        <>
          <h2>Phasengerechte Sprache</h2>
          <div className="card">
            <p>{feedback.phase_language}</p>
            <p className="phase-note">
              Ein Gespräch läuft in drei Phasen ab – Einstieg, Anliegen, Abschluss – und
              der Tonfall soll mitgehen: warm, dann sachlich, dann wieder warm. Hier geht
              es nur darum, ob er das getan hat, nicht darum, ob die Sache gelöst wurde.
            </p>
          </div>
        </>
      )}
    </>
  );
}

function PointList({
  title,
  points,
  tone,
}: {
  title: string;
  points: FeedbackPoint[];
  tone: "success" | "danger";
}) {
  if (points.length === 0) return null;
  return (
    <>
      <h2>{title}</h2>
      {points.map((point, i) => (
        <div className="card" key={i}>
          <p>
            <span className={`bullet ${tone}`} aria-hidden="true" />
            {point.text}
          </p>
        </div>
      ))}
    </>
  );
}

function Metric({ measurement }: { measurement: Measurement }) {
  // The one metric with a course rather than a single number: loudness across
  // the whole call, as Praat measured it at a fixed rate (ADR 0047/0051).
  const curve = measurement.detail?.curve_db as (number | null)[] | undefined;
  const decimals = DECIMALS[measurement.key] ?? 1;
  return (
    <div className="metric">
      <span className="metric-name">{measurement.name}</span>
      <span className="metric-value">
        {measurement.value.toFixed(decimals)} {measurement.unit ?? ""}
      </span>
      {curve && <Sparkline values={curve} label={`${measurement.name} im Gesprächsverlauf`} />}
    </div>
  );
}
