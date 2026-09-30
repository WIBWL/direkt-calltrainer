import BrandName from "./BrandName";

interface NoAccessViewProps {
  onLogout: () => void;
}

/** What a logged-in User without the `calltrainer-user` role sees instead of
 * the app (ADR 0109). Logging out is the one thing to offer: another account
 * may have the role, and this one gets it only from an administrator. */
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
