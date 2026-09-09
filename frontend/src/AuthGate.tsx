import type { ReactNode } from "react";
import { useEffect } from "react";
import { useAuth } from "react-oidc-context";
import { useLocation } from "react-router-dom";
import AuthStatusView from "./components/AuthStatusView";

import { userManager } from "./auth";
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

  const showsLogin = !auth.isLoading && !auth.activeNavigator && !auth.isAuthenticated;

  // Fetch the discovery document while the login screen is being read, not when
  // the button is pressed. `signinRedirect` needs it and would otherwise fetch
  // it there, putting a round trip to Keycloak (~200 ms) between the click and
  // the navigation, which reads as a stalled button. MetadataService keeps it in
  // memory, so the press finds it already loaded. Deliberately ignoring a
  // failure: this is a warm-up, and `signinRedirect` fetches it again and
  // surfaces the error on the path that actually depends on it.
  useEffect(() => {
    if (showsLogin) void userManager.metadataService.getMetadata().catch(() => undefined);
  }, [showsLogin]);

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
