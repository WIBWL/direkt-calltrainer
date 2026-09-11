import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { apiFetch } from "../api";
import { useStoredSession } from "../hooks/useStoredSession";
import { ROUTES, type TrainingStart } from "../routes";
import { getTenant, type ReverseScenario } from "../scenarioLibrary";
import { formatOffset } from "../utils/time";
import AppLayout from "./AppLayout";
import { FeedbackReport, MetricSection } from "./FeedbackView";
import ScenarioEditor from "./ScenarioEditor";

/**
 * One past training, opened from the history (F-48): the wrap-up that was
 * generated for it at the time, the figures behind it, and the Transcript.
 *
 * Read once, never polled. That is the difference from the post-call screen:
 * there a wrap-up really is on its way (ADR 0019), here whatever the database
 * holds is final. Polling a days-old Session would spend a minute claiming
 * something was being created and then call it a failure — which is what this
 * screen used to do.
 *
 * A Session belonging to someone else answers 404 exactly like one that never
 * existed (ADR 0031/0050), so a guessed URL lands on the same screen as a stale
 * bookmark and neither learns anything from it.
 *
 * Both Scenarios a finished training can produce are offered here exactly as
 * they are after the call: the follow-up (F-60) and the reverse (F-61). Each
 * is written when the User asks for it rather than in the background, which is
 * what makes them offerable about a training read weeks later just as well as
 * about one that has just ended.
 */
export default function PastSessionView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { detail, state, reload } = useStoredSession(sessionId ?? null);
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);
  // Open only while the follow-up is being edited; the editor needs the
  // company name to decide whether sharing is on offer at all (ADR 0060).
  const [editingId, setEditingId] = useState<string | null>(null);
  const [tenantName, setTenantName] = useState<string | null>(null);

  useEffect(() => {
    getTenant()
      .then((t) => setTenantName(t.name))
      .catch(() => setTenantName(null)); // no company, no sharing toggle
  }, []);

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

  // Back to the history rather than to the now-empty page this was. Replacing
  // the entry means Back does not return to a training that no longer exists.
  const remove = async () => {
    setDeleting(true);
    setDeleteFailed(false);
    try {
      await apiFetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
      navigate(ROUTES.profile, { replace: true });
    } catch (e) {
      console.debug("[delete session] failed", e);
      setDeleteFailed(true);
      setDeleting(false);
    }
  };

  // Still a link, not a button: it navigates, so middle-click and "open in new
  // tab" have to keep working. Only its appearance is the button's.
  const backLink = (
    <Link to={ROUTES.profile} className="back-to-start-button page-back-button">
      Zurück zum Profil
    </Link>
  );

  if (state === "missing") {
    return (
      <AppLayout>
        {backLink}
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
        {backLink}
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
        {backLink}
        <h1>Training</h1>
        <p className="muted">Wird geladen …</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      {backLink}
      <h1>{detail.scenario}</h1>
      <p className="page-lead">
        {/* Which side the User was on (ADR 0070) — the transcript below reads
            very differently depending on it. */}
        {detail.reverse
          ? `Rollentausch: Sie riefen an, ${detail.persona} nahm ab`
          : `Gespräch mit ${detail.persona}`}
      </p>

      {detail.feedback ? (
        <FeedbackReport
          detail={detail}
          // Re-read after one is written, so the card survives a reload of
          // this page as the row the detail route now carries.
          followUp={{ onEdit: setEditingId, onStart: startFollowUp, onCreated: reload }}
          sessionId={sessionId ?? null}
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
          <MetricSection measurements={detail.measurements} />
        </>
      )}

      <h2>Gesprächsprotokoll</h2>
      {detail.turns.length > 0 ? (
        <div className="card">
          {detail.turns.map((turn) => (
            <p className="transcript-line" key={turn.turn_id}>
              <span className="transcript-time">{formatOffset(turn.start_offset_ms)}</span>
              <span>
                <strong>{turn.speaker === "user" ? "Du" : detail.persona}:</strong>{" "}
                {turn.transcript}
              </span>
            </p>
          ))}
        </div>
      ) : (
        <div className="card">
          <p className="muted">Für dieses Training wurde kein Gesprächsprotokoll gespeichert.</p>
        </div>
      )}

      {/* At the bottom, after everything it would destroy. Putting it beside
          the heading would make it the first thing in reach on a screen the
          user opened in order to read. */}
      <section className="session-delete">
        {confirming ? (
          <>
            <p>
              <strong>Dieses Training löschen?</strong> Gesprächsprotokoll, Kennzahlen und
              Auswertung werden entfernt. Das lässt sich nicht rückgängig machen.
            </p>
            <div className="consent-confirm-actions">
              <button
                type="button"
                className="consent-button consent-button-danger"
                onClick={() => void remove()}
                disabled={deleting}
              >
                {deleting ? "Wird gelöscht …" : "Endgültig löschen"}
              </button>
              <button
                type="button"
                className="consent-button consent-button-secondary"
                onClick={() => setConfirming(false)}
                disabled={deleting}
              >
                Abbrechen
              </button>
            </div>
          </>
        ) : (
          <button
            type="button"
            className="session-delete-trigger"
            onClick={() => setConfirming(true)}
          >
            Dieses Training löschen
          </button>
        )}

        {deleteFailed && (
          <p className="consent-error">
            Das Training konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.
          </p>
        )}
      </section>

      {/* Re-read after a save: the card above carries the title and teaser as
          they were when this page loaded. */}
      {editingId !== null && (
        <ScenarioEditor
          scenarioId={editingId}
          tenantName={tenantName}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            reload();
          }}
          onRefresh={reload}
        />
      )}
    </AppLayout>
  );
}
