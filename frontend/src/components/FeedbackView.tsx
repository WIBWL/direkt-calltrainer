import { useState } from "react";

import { ApiError } from "../api";
import type { FeedbackPoint, Measurement } from "../protocol";
import { useSessionFeedback } from "../hooks/useSessionFeedback";
import { createFollowUpDraft, type ScenarioDraft } from "../scenarioLibrary";
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
export default function FeedbackView({
  sessionId,
  onFollowUpDraft,
}: {
  sessionId: string | null;
  /** Hand the drafted follow-up (F-60) to whoever owns the editor. Omitted
   * where there is nowhere to open it. */
  onFollowUpDraft?: (draft: ScenarioDraft) => void;
}) {
  const { detail, state } = useSessionFeedback(sessionId);

  if (!detail?.feedback) {
    return (
      <div className="card">
        <p className="muted">{NOTICE[state]}</p>
      </div>
    );
  }

  const { feedback, measurements } = detail;
  const improvements = feedback.points.filter((p) => p.kind === "improvement");

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
      <PointList title="Daran können Sie arbeiten" points={improvements} tone="danger" />

      {onFollowUpDraft && sessionId && improvements.length > 0 && (
        <FollowUp sessionId={sessionId} onDraft={onFollowUpDraft} />
      )}

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

/** "Folgeszenario erstellen" (F-60): the next exercise, built from the points
 * above. Offered only where there are improvement points — the same condition
 * the backend enforces. The draft opens in the editor and is stored only if the
 * User saves it there. */
function FollowUp({
  sessionId,
  onDraft,
}: {
  sessionId: string;
  onDraft: (draft: ScenarioDraft) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setBusy(true);
    setError(null);
    try {
      onDraft(await createFollowUpDraft(sessionId));
    } catch (e: unknown) {
      // The backend's `detail` is written for the user, so show it as it is.
      setError(
        e instanceof ApiError && e.detail
          ? e.detail
          : "Das Folgeszenario konnte nicht erstellt werden.",
      );
      setBusy(false);
    }
  };

  return (
    <div className="card follow-up">
      <p>
        Aus diesen Punkten lässt sich das nächste Gespräch bauen: eine neue Situation im
        selben Umfeld, die genau das verlangt, was hier gefehlt hat.
      </p>
      <button type="button" className="follow-up-button" disabled={busy} onClick={handleClick}>
        {busy ? "Folgeszenario wird entworfen …" : "Folgeszenario erstellen"}
      </button>
      {busy && (
        <p className="follow-up-note">
          Die KI entwirft den Fall — das dauert einen Moment. Danach können Sie ihn
          prüfen und ändern, bevor er gespeichert wird.
        </p>
      )}
      {error && <p className="follow-up-error">{error}</p>}
    </div>
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
