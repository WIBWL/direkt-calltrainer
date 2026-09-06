import { Link } from "react-router-dom";

import { ROUTES } from "../routes";

interface LoginViewProps {
  errorMessage?: string | undefined;
  onLogin: () => void;
}

export default function LoginView({
  errorMessage,
  onLogin,
}: LoginViewProps) {
  return (
    <div className="login-page">
      <header className="login-header">
        <div className="login-brand">
          <span className="login-brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>

          <span className="login-brand-name">Calltrainer</span>
        </div>

        <span className="login-prototype-badge">UI-Prototyp</span>
      </header>

      <main className="login-main">
        <section className="login-hero" aria-labelledby="login-hero-title">
          <div className="login-hero-badge">
            <span className="login-hero-badge-dot" aria-hidden="true" />
            KI-gestütztes Gesprächstraining
          </div>

          <h1 id="login-hero-title" className="login-hero-title">
            Trainieren Sie Kundengespräche, bevor sie zählen.
          </h1>

          <p className="login-hero-description">
            Üben Sie realistische Gesprächssituationen mit KI, erhalten Sie
            direktes Feedback und entwickeln Sie Ihre Gesprächsführung Schritt
            für Schritt weiter.
          </p>

          <div className="login-training-preview">
            <div className="login-training-header">
              <div className="login-training-person">
                <span className="login-training-avatar" aria-hidden="true">
                  AB
                </span>

                <div>
                  <div className="login-training-name">Anna Berger</div>
                  <div className="login-training-meta">
                    Reklamation · anspruchsvolle Kundin
                  </div>
                </div>
              </div>

              <span className="login-training-status">Training aktiv</span>
            </div>

            <div
              className="login-training-wave"
              aria-label="Beispielhafte Sprachaktivität"
            >
              {Array.from({ length: 18 }, (_, index) => (
                <span key={index} />
              ))}
            </div>

            <div className="login-training-footer">
              <div>
                <strong>02:14</strong>
                <span>Gesprächsdauer</span>
              </div>

              <div>
                <strong>Live-Feedback</strong>
                <span>Nach Trainingsende</span>
              </div>
            </div>
          </div>
        </section>

        <section className="login-card" aria-labelledby="login-title">
          <div className="login-card-eyebrow">Anmeldung</div>

          <h2 id="login-title" className="login-card-title">
            Willkommen zurück
          </h2>

          <p className="login-card-description">
            Melden Sie sich an, um Ihr nächstes Training zu starten.
          </p>

          <div className="login-auth-note">
            <span className="login-auth-icon" aria-hidden="true">
              🔒
            </span>

            <span>
              Die Anmeldung erfolgt über Ihren sicheren Unternehmenszugang. Sie
              werden dafür kurz weitergeleitet.
            </span>
          </div>

          {errorMessage ? (
            <div className="login-error" role="alert">
                <strong>Anmeldung fehlgeschlagen</strong>
                <span>{errorMessage}</span>
            </div>
        ) : null}

          <button
            type="button"
            className="login-submit-button"
            onClick={onLogin}
          >
            <span>Jetzt anmelden</span>
            <span aria-hidden="true">→</span>
          </button>

          <p className="login-redirect-hint">
            Nach erfolgreicher Anmeldung kehren Sie automatisch zum Calltrainer
            zurück.
          </p>

          <div className="login-divider">
            <span>Sicherer Zugang</span>
          </div>

          <p className="login-privacy-note">
            Mit der Anmeldung bestätigen Sie, dass Sie die{" "}
            <Link to={ROUTES.privacy}>Datenschutzhinweise</Link> gelesen haben.
          </p>
        </section>
      </main>
    </div>
  );
}
