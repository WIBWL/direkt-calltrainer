import { useEffect } from "react";

import LegalPage from "../LegalPage";

/** Old legal URLs, which only forward: a published legal URL must not 404. `replace`, so Back does not bounce. */
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
