import { useState } from "react";

import InfoDetails from "./InfoDetails";
import PrivacyLink from "./PrivacyLink";
import ProcessingNotice from "./ProcessingNotice";

/** Asked once (ADR 0066). Declining leaves the trainer fully usable, so both buttons carry equal weight. */
export default function ConsentDialog({
  onDecide,
  saving,
}: {
  onDecide: (granted: boolean) => Promise<unknown>;
  saving: boolean;
}) {
  const [failed, setFailed] = useState(false);

  // Awaited, or a rejection goes unhandled and the click seems to have worked.
  const decide = async (granted: boolean) => {
    setFailed(false);
    try {
      await onDecide(granted);
    } catch {
      setFailed(true);
    }
  };

  return (
    <div className="consent-backdrop" role="dialog" aria-modal="true" aria-labelledby="consent-title">
      <div className="consent-dialog">
        <h1 id="consent-title">Dürfen wir Ihre Trainings speichern?</h1>

        <p>
          Von Ihren Trainings, auch abgebrochenen, speichern wir Gesprächsprotokoll, Kennzahlen
          und Auswertung, verknüpft mit Ihrem Konto.
        </p>

        <p className="consent-highlight">
          <strong>Ihre Tonaufnahme wird nicht gespeichert.</strong>
        </p>

        <p className="consent-note">
          Ohne Zustimmung trainieren Sie genauso, es wird nur nichts abgelegt. Jederzeit im
          Profil änderbar.
        </p>

        <InfoDetails label="Was das im Einzelnen bedeutet">
          <p>
            Ohne Zustimmung sehen Sie Ihr Gesprächsprotokoll direkt nach dem Gespräch, bekommen
            aber keine Auswertung, und in Ihrer Trainingshistorie erscheint das Gespräch nicht.
          </p>
          <p>
            Widerrufen Sie später, werden die bis dahin gespeicherten Trainings gelöscht.
            Gespeicherte Trainings werden außerdem nach sechs Monaten automatisch gelöscht.
          </p>

          <ProcessingNotice compact />

          <p>
            Ausführlich in der <PrivacyLink>Datenschutzerklärung</PrivacyLink>.
          </p>
        </InfoDetails>

        {failed && (
          <p className="consent-error">
            Ihre Auswahl konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.
          </p>
        )}

        <div className="consent-actions">
          <button
            type="button"
            className="consent-button consent-button-primary"
            onClick={() => void decide(true)}
            disabled={saving}
          >
            Ja, Trainings speichern
          </button>
          <button
            type="button"
            className="consent-button consent-button-secondary"
            onClick={() => void decide(false)}
            disabled={saving}
          >
            Nein, nichts speichern
          </button>
        </div>
      </div>
    </div>
  );
}
