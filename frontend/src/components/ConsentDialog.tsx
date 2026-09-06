import { useState } from "react";

import ProcessingNotice from "./ProcessingNotice";

/**
 * The storage decision, asked once and answerable either way (ADR 0060).
 *
 * Blocking, because it has to be answered before the first training can be
 * stored — but *not* a wall in front of the product. Declining is a real
 * option that leaves the trainer fully usable, which is the point: a consent
 * that has to be given before anything works at all is not freely given, and
 * would be the weaker legal basis for exactly the data it is meant to cover.
 *
 * The two buttons are therefore given equal weight. A greyed-out "no" beside a
 * bright "yes" is a dark pattern, and it would undermine the consent it
 * collects.
 */
export default function ConsentDialog({
  onDecide,
  saving,
}: {
  onDecide: (granted: boolean) => Promise<unknown>;
  saving: boolean;
}) {
  const [failed, setFailed] = useState(false);

  // Awaited, not fired and forgotten: a rejected promise from a synchronous
  // try/catch would go unhandled and the dialog would sit there looking as if
  // the click had worked.
  const decide = async (granted: boolean) => {
    setFailed(false);
    try {
      await onDecide(granted);
    } catch {
      setFailed(true);
    }
  };

  return (
    // aria-modal + role=dialog: the rest of the page is inert behind it, and a
    // screen reader should say so rather than reading the app underneath.
    <div className="consent-backdrop" role="dialog" aria-modal="true" aria-labelledby="consent-title">
      <div className="consent-dialog">
        <h1 id="consent-title">Dürfen wir Ihre Trainings speichern?</h1>

        <p>
          Der Calltrainer kann Ihre abgeschlossenen Trainings speichern, damit Sie sie später
          wieder ansehen können. Gespeichert werden dann das Gesprächsprotokoll als Text, die
          gemessenen Kennzahlen und Ihre Rückmeldung, verknüpft mit Ihrem Konto.
        </p>

        <p className="consent-highlight">
          <strong>Ihre Tonaufnahme wird nicht gespeichert.</strong> Der Ton wird während des
          Gesprächs ausgewertet und danach verworfen.
        </p>

        <p>
          Sie können auch ohne Zustimmung trainieren. Dann wird nach dem Gespräch nichts
          abgelegt. Sie sehen Ihr Gesprächsprotokoll direkt im Anschluss, bekommen aber keine
          Auswertung, und in Ihrer Trainingshistorie erscheint das Gespräch nicht.
        </p>

        <ProcessingNotice compact />

        <p className="consent-note">
          Sie können das jederzeit im Profil ändern. Widerrufen Sie später, werden die bis
          dahin gespeicherten Trainings gelöscht. Gespeicherte Trainings werden außerdem nach
          sechs Monaten automatisch gelöscht.
        </p>

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
