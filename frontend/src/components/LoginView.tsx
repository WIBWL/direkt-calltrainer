interface LoginViewProps {
  errorMessage?: string | undefined;
  onLogin: () => void;
}

export default function LoginView({
  errorMessage,
  onLogin,
}: LoginViewProps) {
  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Anmeldung erforderlich</h1>

      <div className="card">
        <p>Bitte melden Sie sich an, um ein Training zu starten.</p>

        {errorMessage ? (
          <p id="status" className="error">
            Anmeldung fehlgeschlagen: {errorMessage}
          </p>
        ) : null}
      </div>

      <button
        type="button"
        className="start-call-button"
        style={{ marginTop: "1.5rem" }}
        onClick={onLogin}
      >
        Mit Keycloak anmelden
      </button>
    </>
  );
}