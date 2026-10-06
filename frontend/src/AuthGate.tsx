import type { ReactNode } from "react";
import { useEffect } from "react";
import { useAuth } from "react-oidc-context";
import { useLocation } from "react-router-dom";
import AuthStatusView from "./components/AuthStatusView";

import { userManager } from "./auth";
import LoginView from "./components/LoginView";
import NoAccessView from "./components/NoAccessView";
import { oidcClientId } from "./oidcConfig";
import { holdsRequiredRole } from "./utils/access";

/** Children only for a logged-in user with the role (ADR 0109). `isLoading`
 * first, so the login prompt does not flash on every load. */
export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();

  const location = useLocation();

  const showsLogin = !auth.isLoading && !auth.activeNavigator && !auth.isAuthenticated;

  // Warms the discovery document; `signinRedirect` surfaces any error itself.
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
    if (!holdsRequiredRole(auth.user?.access_token ?? "", oidcClientId)) {
      return <NoAccessView onLogout={() => void auth.signoutRedirect()} />;
    }
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
