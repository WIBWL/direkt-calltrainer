import BrandName from "./BrandName";

interface NoAccessViewProps {
  onLogout: () => void;
}

/** Without the `calltrainer-user` role (ADR 0109); logging out is the one offer. */
export default function NoAccessView({ onLogout }: NoAccessViewProps) {
  return (
    <div className="auth-status-page" role="alert">
      <div className="auth-status-card">
        <div>
          <strong>
            <BrandName />
          </strong>
          <span>
            Ihr Konto ist für den Calltrainer nicht freigeschaltet. Bitte wenden
            Sie sich an die Person, die Ihren Zugang verwaltet.
          </span>
          <button type="button" className="login-submit-button" onClick={onLogout}>
            Abmelden
          </button>
        </div>
      </div>
    </div>
  );
}
