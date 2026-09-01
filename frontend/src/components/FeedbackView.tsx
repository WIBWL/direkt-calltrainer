import type { Feedbackpunkt, Messung } from "../protocol";
import { useSessionFeedback } from "../hooks/useSessionFeedback";
import Sparkline from "./Sparkline";

/** How many decimals a metric reads naturally in. Counts are whole things;
 * seconds and percentages are not. */
const DECIMALS: Record<string, number> = { fragen: 0, wortanzahl: 0, tempo: 0, redeanteil: 0 };

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

  const { feedback, messungen } = detail;

  return (
    <>
      <div className="card">
        <p>{feedback.zusammenfassung}</p>
      </div>

      <PointList
        title="Das lief gut"
        points={feedback.punkte.filter((p) => p.art === "staerke")}
        tone="success"
      />
      <PointList
        title="Daran können Sie arbeiten"
        points={feedback.punkte.filter((p) => p.art === "verbesserung")}
        tone="danger"
      />

      {messungen.length > 0 && (
        <>
          <h2>Zahlen zum Gespräch</h2>
          <div className="card">
            <div className="metric-grid">
              {messungen.map((m) => (
                <Metric key={m.schluessel} messung={m} />
              ))}
            </div>
            <p className="metric-disclaimer">
              Reine Messwerte, ohne Zielbereich: für diese Nutzergruppe gibt es keinen
              belegten Normwert, an dem sie zu messen wären.
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
  points: Feedbackpunkt[];
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

function Metric({ messung }: { messung: Messung }) {
  // The one metric with a course rather than a single number: loudness across
  // the whole call, as Praat measured it at a fixed rate (ADR 0047/0051).
  const verlauf = messung.detail?.verlauf_db as (number | null)[] | undefined;
  const decimals = DECIMALS[messung.schluessel] ?? 1;
  return (
    <div className="metric">
      <span className="metric-name">{messung.bezeichnung}</span>
      <span className="metric-value">
        {messung.wert.toFixed(decimals)} {messung.einheit ?? ""}
      </span>
      {verlauf && <Sparkline values={verlauf} label={`${messung.bezeichnung} im Gesprächsverlauf`} />}
    </div>
  );
}
