import type { ReactNode } from "react";
import { useEffect } from "react";
import { useAuth } from "react-oidc-context";
import { useLocation } from "react-router-dom";
import AuthStatusView from "./components/AuthStatusView";

import { userManager } from "./auth";
import LoginView from "./components/LoginView";

/**
 * Renders `children` only for an authenticated user; a splash while the session
 * is restored or a redirect is in flight, else the login screen. `isLoading` is
 * checked first so the login prompt does not flash on every page load.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();

  // The router's location, not window.location: inside a Router the two agree,
  // but reading it here is what makes the dependency explicit.
  const location = useLocation();

  const showsLogin = !auth.isLoading && !auth.activeNavigator && !auth.isAuthenticated;

  // Warm up the discovery document while the login screen is read, so the
  // button press does not wait ~200 ms on Keycloak. A failure is ignored:
  // `signinRedirect` fetches it again and surfaces the error there.
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
