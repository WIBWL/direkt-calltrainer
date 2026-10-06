import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import { ROUTES, type TrainingStart } from "../routes";
import type { ReverseScenario } from "../scenarioLibrary";
import AppLayout from "./AppLayout";
import DeleteSessionPrompt, { useSessionDeletion } from "./DeleteSessionPrompt";
import FeedbackScreen, { transcriptFromTurns } from "./FeedbackScreen";
import FeedbackReport from "./FeedbackReport";
import MetricSection from "./MetricSection";

/** One past training (F-48). Read once, never polled: the stored state is final (ADR 0019). */
export default function PastSessionView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { detail, state, reload } = useStoredSession(sessionId ?? null);
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  // Replaced, so Back does not return to a deleted training.
  const deletion = useSessionDeletion(sessionId, () =>
    navigate(ROUTES.profile, { replace: true }),
  );

  // Handed to the training route (TrainingStart), with this training's Persona.
  const startFollowUp = (scenarioId: string, personaId: string) => {
    const start: TrainingStart = { scenarioId, personaId };
    navigate(ROUTES.training, { state: { start } });
  };

  // The reverse (F-61, ADR 0070) leaves the same way.
  const startReverse = (reverse: ReverseScenario) => {
    if (!detail) return;
    const start: TrainingStart = {
      scenarioId: reverse.id,
      personaId: detail.persona_id,
      reverse: true,
    };
    navigate(ROUTES.training, { state: { start } });
  };

  // A link styled as a button, so new-tab still works; shown above the report and in the actions row.
  const backLink = (
    <Link to={ROUTES.profile} className="back-to-start-button">
      Zurück zum Profil
    </Link>
  );
  const topBackLink = (
    <Link to={ROUTES.profile} className="back-to-start-button page-back-button">
      Zurück zum Profil
    </Link>
  );

  if (state === "missing") {
    return (
      <AppLayout>
        {topBackLink}
        <h1>Training nicht gefunden</h1>
        <div className="card">
          <p>
            Zu diesem Link gibt es kein Training. Möglicherweise wurde es gelöscht, oder der
            Link gehört nicht zu Ihrem Konto.
          </p>
        </div>
      </AppLayout>
    );
  }

  if (state === "failed") {
    return (
      <AppLayout>
        {topBackLink}
        <h1>Training</h1>
        <div className="card">
          <p>Das Training konnte nicht geladen werden. Bitte versuchen Sie es später erneut.</p>
        </div>
      </AppLayout>
    );
  }

  if (state === "loading" || detail === null) {
    return (
      <AppLayout>
        {topBackLink}
        <h1>Training</h1>
        <p className="muted">Wird geladen …</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout pageClassName="feedback-page">
      {topBackLink}
      <FeedbackScreen
        transcript={transcriptFromTurns(detail.turns)}
        personaName={detail.persona}
        scenarioName={detail.scenario}
        detail={detail}
        actions={backLink}
        feedback={
          detail.feedback ? (
            <FeedbackReport
              detail={detail}
              // Re-read, so the card survives a reload.
              followUp={{ onStart: startFollowUp, onCreated: reload }}
              onReverse={startReverse}
            />
          ) : (
            <>
              <div className="card">
                <p className="muted">
                  Zu diesem Gespräch gibt es keine Auswertung. Sie ist damals nicht zustande
                  gekommen. Das Gesprächsprotokoll und die Zahlen unten sind vollständig.
                </p>
              </div>
              {/* Measured during the call (ADR 0048), so shown without a wrap-up too. */}
              <MetricSection
                measurements={detail.measurements}
                findings={detail.findings}
                notes={detail.metric_notes}
                sessionId={detail.session_id}
                segments={detail.segments}
              />
            </>
          )
        }
      >
        {/* At the bottom, after everything it would destroy. */}
        <section className="session-delete">
          {confirming ? (
            <DeleteSessionPrompt
              deleting={deletion.deleting}
              failed={deletion.failed}
              onConfirm={() => void deletion.remove()}
              onCancel={() => setConfirming(false)}
            />
          ) : (
            <button
              type="button"
              className="session-delete-trigger"
              onClick={() => setConfirming(true)}
            >
              Dieses Training löschen
            </button>
          )}
        </section>
      </FeedbackScreen>
    </AppLayout>
  );
}
