import { useEffect } from "react";

import LegalPage from "../LegalPage";

/**
 * `/impressum`, `/datenschutz` and `/barrierefreiheit`, which now only forward.
 *
 * The imprint and the accessibility statement were copies of the project's own
 * pages here, the privacy statement a full document of its own. None is left:
 * every mention in the interface links the project's page straight out
 * (`ProjectPageLink`), so nothing in the app reaches these routes any more.
 * What the old texts said is in the git history, and what the target pages
 * still owe a reader is listed in `docs/deployment.md`.
 *
 * The routes stay all the same, because a legal URL that has been published
 * once must not 404: a registry or the project site may point at it. `replace`
 * rather than `assign`, so Back does not bounce the reader between the two, and
 * the sentence below is what a reader sees if the redirect is blocked or
 * JavaScript never ran.
 */
export default function ProjectPageRedirect({ title, url }: { title: string; url: string }) {
  useEffect(() => {
    window.location.replace(url);
  }, [url]);

  return (
    <LegalPage title={title}>
      <div className="legal-body">
        <p>
          Diese Seite wird beim Projekt EFRE DiReKT gepflegt. Sie werden dorthin
          weitergeleitet.
        </p>
        <p>
          <a href={url}>{title} auf efre-direkt.de öffnen</a>
        </p>
      </div>
    </LegalPage>
  );
}
