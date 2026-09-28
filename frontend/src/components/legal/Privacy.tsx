import LegalPage from "../LegalPage";
import { Link } from "react-router-dom";

import { ROUTES } from "../../routes";

/** Where the privacy statement lives. The EFRE DiReKT project's own page, which
 *  is the statement of the responsible body for everything under the project. */
export const PRIVACY_URL = "https://efre-direkt.de/privacy/";

/**
 * The privacy statement, which is no longer here.
 *
 * It used to be a full statement of its own, derived from
 * https://efre-direkt.de/privacy/ and adapted to what the Calltrainer actually
 * processes. It is now a referral to that page, so that one document is
 * maintained instead of two that can drift apart.
 *
 * The route stays rather than the footer linking out directly: three places
 * point at it (`AppFooter`, `ConsentDialog`, `ProfileView`), and the consent
 * dialog in particular has to reference a notice that exists. A route that
 * disappeared would break the reference the consent rests on.
 *
 * **What this page deliberately does not do is describe the processing.** That
 * is the point of the change, and it is also its one risk: as of the change,
 * the target page describes a website — a contact form, ticketing, a mailing
 * list — and says nothing about speech leaving the browser for the DiReKT
 * gateway and KugelAudio, about consent-gated storage of transcripts, the
 * six-month retention, the focus goals stored beside the trainings, or the
 * consent log that outlives them. Until that content is on the target page, the
 * application's own processing has no Art. 13 notice anywhere.
 *
 * So: this file is not where a description of the processing belongs any more,
 * and adding one back here would recreate the second document. It belongs on
 * the target page. Whoever restores it there should note that the statement
 * this page replaced said an abandoned call is not stored, which is wrong —
 * `persistence.py` stores it as `aborted` with its full transcript (ADR 0034's
 * amendment), it is only not counted.
 */
export default function Privacy() {
  return (
    <LegalPage title="Datenschutzerklärung">
      <div className="legal-body">
        <p>
          Die Datenschutzerklärung für den Calltrainer ist Teil der Erklärung des Projekts
          EFRE DiReKT. Sie wird dort gepflegt, damit es nur eine gibt.
        </p>
        <p>
          <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer">
            Datenschutzerklärung auf efre-direkt.de öffnen
          </a>{" "}
          (öffnet in einem neuen Tab)
        </p>
        <p>
          Was zu Ihren Trainings gespeichert ist, können Sie jederzeit{" "}
          <Link to={ROUTES.profile}>in Ihrem Profil</Link> einsehen, herunterladen und
          löschen. Dort ändern Sie auch Ihre Einwilligung zur Speicherung und die
          automatische Löschung nach sechs Monaten.
        </p>
      </div>
    </LegalPage>
  );
}
