import type { ReactNode } from "react";
import { useAuth } from "react-oidc-context";
import { useLocation } from "react-router-dom";
import AuthStatusView from "./components/AuthStatusView";

import LoginView from "./components/LoginView";

/**
 * Renders `children` only for an authenticated user. While the session is being
 * restored or a redirect is in flight it shows a splash; otherwise the login
 * screen. Branching on `isLoading` first avoids flashing the login prompt on
 * every page load while the session is silently restored from storage.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();

  // The router's location, not window.location: inside a Router the two agree,
  // but reading it here is what makes the dependency explicit.
  const location = useLocation();

  if (auth.isLoading || auth.activeNavigator) {
  return (
    <AuthStatusView
      message={
        auth.activeNavigator
          ? "Sie werden zur Anmeldung weitergeleitet …"
          : "Ihre Sitzung wird geladen …"
      }
    />
  );
}

  if (auth.isAuthenticated) {
    return <>{children}</>;
  }

  return (
    <LoginView
      errorMessage={auth.error?.message}
      onLogin={() =>
        void auth.signinRedirect({
          state: { returnTo: location.pathname + location.search },
        })
      }
    />
  );
}
