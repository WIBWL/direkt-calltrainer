import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import PrivacyLink from "./PrivacyLink";

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
          {/* Router links, not <a href>: a plain href reloads the whole app,
              which on the way out of a finished wrap-up would discard it. */}
          <Link to={ROUTES.imprint}>Impressum</Link>
          {/* The exception, and it leaves the app on purpose: the statement is
              the project's own page (`PrivacyLink`). A new tab for the reason
              above — a finished wrap-up must survive the trip. */}
          <PrivacyLink>Datenschutz</PrivacyLink>
          <Link to={ROUTES.accessibility}>Barrierefreiheit</Link>
          <Link to={ROUTES.notes}>Wichtige Hinweise</Link>
        </nav>
      </div>
    </footer>
  );
}
