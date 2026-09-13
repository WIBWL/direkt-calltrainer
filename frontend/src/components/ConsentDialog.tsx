import { useState } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import InfoDetails from "./InfoDetails";
import ProcessingNotice from "./ProcessingNotice";

/**
 * The storage decision, asked once and answerable either way (ADR 0066).
 *
 * Blocking, because it must be answered before the first training can be
 * stored — but *not* a wall in front of the product. Declining leaves the
 * trainer fully usable, which is the point: a consent that has to be given
 * before anything works is not freely given, and would be the weaker legal
 * basis for exactly the data it covers.
 *
 * The two buttons therefore carry equal weight; a greyed-out "no" beside a
 * bright "yes" is a dark pattern that would undermine the consent it collects.
 *
 * Short on purpose: what the decision turns on sits above the buttons in four
 * lines and the background one click away. A notice long enough to be skipped
 * informs nobody, and an unread wall of text is the weaker consent.
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
          Von abgeschlossenen Trainings speichern wir Gesprächsprotokoll, Kennzahlen und
          Auswertung, verknüpft mit Ihrem Konto.
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
            Ausführlich in der <Link to={ROUTES.privacy}>Datenschutzerklärung</Link>.
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
