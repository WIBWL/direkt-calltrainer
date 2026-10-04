import { useEffect } from "react";

import { PRIVACY_URL } from "../../routes";
import LegalPage from "../LegalPage";

/**
 * `/datenschutz`, which now only forwards.
 *
 * The statement was a full document of its own here, then a page referring to
 * the project's own one. Neither is left: every mention in the interface links
 * `PRIVACY_URL` straight out (`PrivacyLink`), so nothing in the app reaches
 * this route any more. What the old text said is in the git history, and what
 * the target page still owes a reader is listed in `docs/deployment.md`.
 *
 * The route stays all the same, because a legal URL that has been published
 * once must not 404: an imprint, a registry or the project site may point at
 * it. `replace` rather than `assign`, so Back does not bounce the reader
 * between the two, and the sentence below is what a reader sees if the redirect
 * is blocked or JavaScript never ran.
 */
export default function Privacy() {
  useEffect(() => {
    window.location.replace(PRIVACY_URL);
  }, []);

  return (
    <LegalPage title="Datenschutzerklärung">
      <div className="legal-body">
        <p>
          Die Datenschutzerklärung wird beim Projekt EFRE DiReKT gepflegt. Sie werden
          dorthin weitergeleitet.
        </p>
        <p>
          <a href={PRIVACY_URL}>Datenschutzerklärung auf efre-direkt.de öffnen</a>
        </p>
      </div>
    </LegalPage>
  );
}
