import type { User } from "oidc-client-ts";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import App from "./App";
import { AuthGate } from "./AuthGate";
import { userManager } from "./auth";
import "./index.css";

const onSigninCallback = (user: User | undefined) => {
  // Return to the page originally requested (captured in `state` at
  // signinRedirect time) and strip the code/state from the URL — the latter is
  // required for silent renew to work.
  const returnTo = (user?.state as { returnTo?: string } | undefined)?.returnTo ?? "/";
  window.history.replaceState({}, document.title, returnTo);
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider userManager={userManager} onSigninCallback={onSigninCallback}>
      <AuthGate>
        <App />
      </AuthGate>
    </AuthProvider>
  </StrictMode>,
);
