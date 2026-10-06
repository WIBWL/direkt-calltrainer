import { useState } from "react";

import { useConsentContext } from "../ConsentContext";

/** Withdrawal deletes the stored trainings (ADR 0066), so it is confirmed; granting is not. */
export default function ConsentSettings() {
  const { consent, saving, decide } = useConsentContext();
  const [confirming, setConfirming] = useState(false);
  const [deleted, setDeleted] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);

  if (!consent) {
    return (
      <p className="muted">
        Ihre Einstellung konnte nicht geladen werden. Bitte laden Sie die Seite neu.
      </p>
    );
  }

  const run = async (granted: boolean) => {
    setFailed(false);
    try {
      const removed = await decide(granted);
      setConfirming(false);
      setDeleted(granted ? null : removed);
    } catch {
      setFailed(true);
    }
  };

  return (
    <>
      <p className="consent-status">
        <span className={`chip ${consent.allows_storage ? "chip-success" : "chip-absent"}`}>
          {consent.allows_storage ? "Speicherung erlaubt" : "Speicherung widerrufen"}
        </span>
      </p>

      {/* What is stored is said once, in the "Ihre Daten" card. */}
      {consent.allows_storage ? (
        <p>Abgeschlossene Trainings werden gespeichert.</p>
      ) : (
        <p>
          Es wird nichts gespeichert. Trainieren geht weiter, nur ohne Auswertung und ohne
          Historie.
        </p>
      )}

      {deleted !== null && (
        <p className="consent-result">
          {deleted === 0
            ? "Es waren keine gespeicherten Trainings vorhanden."
            : `${deleted} gespeicherte${deleted === 1 ? "s Training wurde" : " Trainings wurden"} gelöscht.`}
        </p>
      )}

      {failed && (
        <p className="consent-error">
          Ihre Auswahl konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.
        </p>
      )}

      {consent.allows_storage ? (
        confirming ? (
          <div className="consent-confirm">
            {/* Reverses are named: a withdrawal takes them too, a single deletion does not (ADR 0070). */}
            <p>
              <strong>Widerrufen und alle gespeicherten Trainings löschen?</strong> Ihre bisherigen
              Gesprächsprotokolle, Kennzahlen und Rückmeldungen werden dabei entfernt, ebenso Ihre
              Rollentausch-Szenarien samt der Unterlagen darin. Das lässt sich nicht rückgängig
              machen.
            </p>
            <div className="consent-confirm-actions">
              <button
                type="button"
                className="consent-button consent-button-danger"
                onClick={() => void run(false)}
                disabled={saving}
              >
                {saving ? "Wird ausgeführt …" : "Widerrufen und löschen"}
              </button>
              <button
                type="button"
                className="cancel-button"
                onClick={() => setConfirming(false)}
                disabled={saving}
              >
                Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="consent-button consent-button-secondary"
            onClick={() => setConfirming(true)}
          >
            Einwilligung widerrufen
          </button>
        )
      ) : (
        <button
          type="button"
          className="consent-button consent-button-primary"
          onClick={() => void run(true)}
          disabled={saving}
        >
          {saving ? "Wird gespeichert …" : "Speicherung wieder erlauben"}
        </button>
      )}
    </>
  );
}
