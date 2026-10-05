import { Link } from "react-router-dom";

import { ACCESSIBILITY_URL, IMPRINT_URL, ROUTES } from "../routes";
import PrivacyLink from "./PrivacyLink";
import ProjectPageLink from "./ProjectPageLink";

// The shared footer keeps legal information consistent across all training screens.
export default function AppFooter() {
  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <div className="app-footer-information">
          <span className="app-footer-copyright">© 2026 Universität Würzburg</span>

          <span className="app-footer-disclaimer">
            KI-gestützter Trainingsprototyp. Ergebnisse dienen ausschließlich zu Übungszwecken.
          </span>
        </div>

        <nav className="app-footer-links" aria-label="Rechtliche Informationen">
          {/* The three legal statements are the project's own pages and leave
              the app on purpose, in a new tab (`ProjectPageLink`). */}
          <ProjectPageLink href={IMPRINT_URL}>Impressum</ProjectPageLink>
          <PrivacyLink>Datenschutz</PrivacyLink>
          <ProjectPageLink href={ACCESSIBILITY_URL}>Barrierefreiheit</ProjectPageLink>
          {/* A router link, not <a href>: a plain href reloads the whole app,
              which on the way out of a finished wrap-up would discard it. */}
          <Link to={ROUTES.notes}>Wichtige Hinweise</Link>
        </nav>
      </div>
    </footer>
  );
}
