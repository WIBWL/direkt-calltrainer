// The shared footer keeps legal information consistent across all training screens.
export default function AppFooter() {
  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <div className="app-footer-information">
          <span className="app-footer-copyright">© 2026 Train to Call</span>

          <span className="app-footer-disclaimer">
            KI-gestützter Trainingsprototyp – Ergebnisse dienen ausschließlich zu Übungszwecken.
          </span>
        </div>

        <nav className="app-footer-links" aria-label="Rechtliche Informationen">
          <a href="/impressum">Impressum</a>
          <a href="/datenschutz">Datenschutz</a>
          <a href="/barrierefreiheit">Barrierefreiheit</a>
          <a href="/hinweise">Wichtige Hinweise</a>
        </nav>
      </div>
    </footer>
  );
}
