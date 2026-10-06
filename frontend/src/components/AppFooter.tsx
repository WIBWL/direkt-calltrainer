import { Link } from "react-router-dom";

import { ACCESSIBILITY_URL, IMPRINT_URL, ROUTES } from "../routes";
import PrivacyLink from "./PrivacyLink";
import ProjectPageLink from "./ProjectPageLink";

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
          {/* The project's own pages, in a new tab. */}
          <ProjectPageLink href={IMPRINT_URL}>Impressum</ProjectPageLink>
          <PrivacyLink>Datenschutz</PrivacyLink>
          <ProjectPageLink href={ACCESSIBILITY_URL}>Barrierefreiheit</ProjectPageLink>
          {/* A router link: a reload would discard a finished wrap-up. */}
          <Link to={ROUTES.notes}>Wichtige Hinweise</Link>
        </nav>
      </div>
    </footer>
  );
}
