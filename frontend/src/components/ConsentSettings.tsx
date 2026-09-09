import { useState } from "react";

import { useConsentContext } from "../ConsentContext";

/**
 * The storage decision on the profile page: what it currently is, and how to
 * change it (ADR 0066).
 *
 * Withdrawal is confirmed in a second step, and the confirmation says what it
 * will destroy — because it does destroy something. Consent is the only basis
 * this application has for keeping the data, so withdrawing it deletes the
 * stored trainings rather than leaving them behind with nothing to justify
 * them. A user who learns that afterwards has learned it too late.
 *
 * Granting again is not confirmed. It takes nothing away, and putting a
 * speed bump in front of the reversible direction only makes the irreversible
 * one look equally routine.
 */
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

      {/* One line each: what is stored, and where it goes, is said once in the
          "Ihre Daten" card below. Repeating it here would be a second copy to
          keep in step with the privacy statement. */}
      {consent.allows_storage ? (
        <p>Abgeschlossene Trainings werden gespeichert.</p>
      ) : (
        <p>
          Es wird nichts gespeichert. Trainieren geht weiter — ohne Auswertung und ohne
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
            {/* Der Rollentausch wird hier eigens genannt (ADR 0070): er ist
                ein Szenario und kein Training, verschwindet beim Widerruf aber
                mit — seine Unterlagen sind aus der eigenen Auswertung
                geschrieben. Beim Löschen eines einzelnen Trainings bleibt er
                dagegen stehen, und genau diese Asymmetrie wäre ohne diesen
                Satz nicht erkennbar. */}
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
