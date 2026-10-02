import type { User } from "oidc-client-ts";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import App from "./App";
import { AuthGate } from "./AuthGate";
import { ConsentProvider } from "./ConsentContext";
import { FocusProvider } from "./FocusContext";
import { ProgressProvider } from "./ProgressContext";
import Accessibility from "./components/legal/Accessibility";
import Imprint from "./components/legal/Imprint";
import Notes from "./components/legal/Notes";
import Privacy from "./components/legal/Privacy";
import PastSessionView from "./components/PastSessionView";
import { ScreenTransitionProvider } from "./components/ScreenTransition";
import ProfileView from "./components/ProfileView";
import ProgressGoalView from "./components/ProgressGoalView";
import ProgressMetricView from "./components/ProgressMetricView";
import ProgressView from "./components/ProgressView";
import SessionMetricView from "./components/SessionMetricView";
import { consumeReturnTo, rememberReturnTo, userManager } from "./auth";
import { ROUTES } from "./routes";
import "./index.css";

const onSigninCallback = (user: User | undefined) => {
  // Keycloak always returns to "/". Stripping `?code=&state=` (needed for silent
  // renew) goes through the History API so the callback stays out of the back
  // stack. Returning to the requested page must NOT happen here: `replaceState`
  // fires no event, so the router would keep the old screen under the new URL.
  // <ReturnToRequestedPage /> below navigates through the router instead.
  const returnTo = (user?.state as { returnTo?: string } | undefined)?.returnTo;
  if (returnTo) rememberReturnTo(returnTo);
  window.history.replaceState({}, document.title, ROUTES.training);
};

/**
 * Sends the user to the page they originally asked for, once. Fires only after
 * a login redirect, the only writer of the stored path.
 */
function ReturnToRequestedPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const target = consumeReturnTo();
    if (target) navigate(target, { replace: true });
  }, [navigate]);

  return null;
}

/**
 * Routes reachable only once the two first-run questions are answered: storage
 * consent (ADR 0066), then focus (ADR 0076). Nested so they come one after the
 * other, the one with a legal basis first.
 */
function ConsentGate() {
  return (
    <ConsentProvider>
      <FocusProvider>
        <Outlet />
      </FocusProvider>
    </ConsentProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider userManager={userManager} onSigninCallback={onSigninCallback}>
        <ReturnToRequestedPage />

        {/* Above the routes on purpose: a transition outlives the screen that
            started it (see ScreenTransition.tsx). */}
        <ScreenTransitionProvider>
          <Routes>
            {/* Public legal pages */}
            <Route path={ROUTES.imprint} element={<Imprint />} />
            <Route path={ROUTES.privacy} element={<Privacy />} />
            <Route path={ROUTES.accessibility} element={<Accessibility />} />
            <Route path={ROUTES.notes} element={<Notes />} />

            {/* Everything below requires authentication. */}
            <Route
              element={
                <AuthGate>
                  <Outlet />
                </AuthGate>
              }
            >
              <Route element={<ConsentGate />}>
                <Route path={ROUTES.training} element={<App />} />
                <Route path={ROUTES.profile} element={<ProfileView />} />
                {/* One history load and selection for the three dashboard
                    screens (ProgressContext.tsx), mounted here so the training
                    flow does not pay for the request, and kept mounted across
                    the three so moving between them refetches nothing. */}
                <Route
                  element={
                    <ProgressProvider>
                      <Outlet />
                    </ProgressProvider>
                  }
                >
                  <Route path={ROUTES.progress} element={<ProgressView />} />
                  <Route path={ROUTES.progressGoal} element={<ProgressGoalView />} />
                  <Route path={ROUTES.progressMetric} element={<ProgressMetricView />} />
                </Route>
                <Route path={ROUTES.session} element={<PastSessionView />} />
                <Route path={ROUTES.sessionMetric} element={<SessionMetricView />} />

                <Route
                  path="*"
                  element={<Navigate to={ROUTES.training} replace />}
                />
              </Route>
            </Route>
          </Routes>
        </ScreenTransitionProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
