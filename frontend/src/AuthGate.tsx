import type { ReactNode } from "react";
import { useAuth } from "react-oidc-context";

/**
 * Renders `children` only for an authenticated user. While the session is being
 * restored or a redirect is in flight it shows a splash; otherwise the login
 * screen. Branching on `isLoading` first avoids flashing the login prompt on
 * every page load while the session is silently restored from storage.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();

  if (auth.isLoading || auth.activeNavigator) {
    return <p id="status">{auth.activeNavigator ? "Weiterleitung …" : "Lädt …"}</p>;
  }

  if (auth.isAuthenticated) {
    return <>{children}</>;
  }

  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Anmeldung erforderlich</h1>
      <div className="card">
        <p>Bitte melden Sie sich an, um ein Training zu starten.</p>
        {auth.error ? (
          <p id="status" className="error">
            Anmeldung fehlgeschlagen: {auth.error.message}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        className="start-call-button"
        style={{ marginTop: "1.5rem" }}
        onClick={() =>
          void auth.signinRedirect({
            state: { returnTo: window.location.pathname + window.location.search },
          })
        }
      >
        Mit Keycloak anmelden
      </button>
    </>
  );
}
