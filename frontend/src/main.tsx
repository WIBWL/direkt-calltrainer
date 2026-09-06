import type { User } from "oidc-client-ts";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import App from "./App";
import { AuthGate } from "./AuthGate";
import { ConsentProvider } from "./ConsentContext";
import Accessibility from "./components/legal/Accessibility";
import Imprint from "./components/legal/Imprint";
import Notes from "./components/legal/Notes";
import Privacy from "./components/legal/Privacy";
import PastSessionView from "./components/PastSessionView";
import ProfileView from "./components/ProfileView";
import { consumeReturnTo, rememberReturnTo, userManager } from "./auth";
import { ROUTES } from "./routes";
import "./index.css";

const onSigninCallback = (user: User | undefined) => {
  // Keycloak always returns to the origin (`oidcRedirectUri`), so the path in
  // the URL bar at this moment is "/" regardless of where the user was headed.
  // Two separate things have to happen, and only one of them is a navigation:
  //
  // Stripping `?code=&state=` is required for silent renew to work, and has to
  // go through the History API because React Router must not treat the OIDC
  // callback as a location worth keeping in the back stack.
  //
  // Returning to the requested page cannot happen here. `replaceState` fires no
  // event, so the router would never learn the path changed — the URL bar would
  // say /profil while the training screen stayed on screen. It is handed to
  // <ReturnToRequestedPage /> below, which navigates through the router.
  const returnTo = (user?.state as { returnTo?: string } | undefined)?.returnTo;
  if (returnTo) rememberReturnTo(returnTo);
  window.history.replaceState({}, document.title, ROUTES.training);
};

/**
 * Sends the user to the page they originally asked for, once.
 *
 * Only ever fires after a login redirect, because that is the only thing that
 * writes the stored path — an ordinary reload of /profil finds nothing here and
 * stays where it is.
 */
function ReturnToRequestedPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const target = consumeReturnTo();
    if (target) navigate(target, { replace: true });
  }, [navigate]);

  return null;
}

/** The routes that may only be reached once the storage decision is answered. */
function ConsentGate() {
  return (
    <ConsentProvider>
      <Outlet />
    </ConsentProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* Router outermost: AuthGate's login button records the current path, so
        it has to be able to read the router's location. */}
    <BrowserRouter>
      <AuthProvider userManager={userManager} onSigninCallback={onSigninCallback}>
        <AuthGate>
          <ReturnToRequestedPage />
          <Routes>
            {/* The legal pages sit outside ConsentProvider. It replaces the
                whole app while the storage decision is unanswered, so a link to
                the privacy statement from inside that dialog would otherwise
                lead straight back to the dialog — the one place the link is
                most likely to be followed from. */}
            <Route path={ROUTES.imprint} element={<Imprint />} />
            <Route path={ROUTES.privacy} element={<Privacy />} />
            <Route path={ROUTES.accessibility} element={<Accessibility />} />
            <Route path={ROUTES.notes} element={<Notes />} />

            {/* Everything below needs the decision: these screens either write
                trainings or read the ones that were written. A pathless layout
                route rather than a nested <Routes>, so the paths stay absolute
                (a descendant <Routes> matches against the *remaining* URL) and
                the provider stays mounted across navigations instead of
                refetching the decision on every route change. */}
            <Route element={<ConsentGate />}>
              <Route path={ROUTES.training} element={<App />} />
              <Route path={ROUTES.profile} element={<ProfileView />} />
              <Route path={ROUTES.session} element={<PastSessionView />} />
              {/* An unknown path is a mistyped or stale link, not an error
                  worth a screen of its own at this size. */}
              <Route path="*" element={<Navigate to={ROUTES.training} replace />} />
            </Route>
          </Routes>
        </AuthGate>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
