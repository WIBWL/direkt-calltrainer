import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import { ROUTES, type TrainingStart } from "../routes";
import type { ReverseScenario } from "../scenarioLibrary";
import AppLayout from "./AppLayout";
import DeleteSessionPrompt, { useSessionDeletion } from "./DeleteSessionPrompt";
import FeedbackScreen, { transcriptFromTurns } from "./FeedbackScreen";
import { FeedbackReport, MetricSection } from "./FeedbackView";

/**
 * One past training from the history (F-48), rendered by `FeedbackScreen` like the post-call screen with other
 * buttons. Read once, never polled: the stored state is final (ADR 0019). A foreign Session is a 404 like a
 * missing one (ADR 0031/0050). Offers the follow-up (F-60) and reverse (F-61), both written on request.
 */
export default function PastSessionView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { detail, state, reload } = useStoredSession(sessionId ?? null);
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  // Back to the history rather than to the now-empty page this was. Replacing
  // the entry means Back does not return to a training that no longer exists.
  const deletion = useSessionDeletion(sessionId, () =>
    navigate(ROUTES.profile, { replace: true }),
  );

  // Starting the follow-up belongs to the training flow, which is another
  // route — so hand it the pairing and go (see TrainingStart). The Persona is
  // the one this training was played with, not a fresh choice.
  const startFollowUp = (scenarioId: string, personaId: string) => {
    const start: TrainingStart = { scenarioId, personaId };
    navigate(ROUTES.training, { state: { start } });
  };

  // The reverse (F-61) leaves by the same door, and is offered here and not
  // only after the call for the reason ADR 0070 gives for storing it at all:
  // standing on the other side of a conversation is worth doing about a
  // training you have gone back to read, not just about the one that has just
  // ended. The Persona is again the one this training was played with.
  const startReverse = (reverse: ReverseScenario) => {
    if (!detail) return;
    const start: TrainingStart = {
      scenarioId: reverse.id,
      personaId: detail.persona_id,
      reverse: true,
    };
    navigate(ROUTES.training, { state: { start } });
  };

  // A link, not a button, so middle-click and "open in new tab" keep working; only styled as a button.
  // Used twice: above the report (so a reader need not scroll back) and in the actions row at the foot.
  // The short screens (not found, failed, loading) have only the upper one.
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
              // Re-read after one is written, so the card survives a reload of
              // this page as the row the detail route now carries.
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
              {/* The figures are measured during the call and stored with the
                  Session (ADR 0047/0048), so they survive a wrap-up that never
                  got written. Withholding them would hide data that is right
                  there. */}
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
        {/* At the bottom, after everything it would destroy. Putting it beside
            the heading would make it the first thing in reach on a screen the
            user opened in order to read. */}
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
