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
import Notes from "./components/legal/Notes";
import ProjectPageRedirect from "./components/legal/ProjectPageRedirect";
import PastSessionView from "./components/PastSessionView";
import { ScreenTransitionProvider } from "./components/ScreenTransition";
import ProfileView from "./components/ProfileView";
import ProgressGoalView from "./components/ProgressGoalView";
import ProgressMetricView from "./components/ProgressMetricView";
import ProgressView from "./components/ProgressView";
import SessionMetricView from "./components/SessionMetricView";
import { consumeReturnTo, rememberReturnTo, userManager } from "./auth";
import { ACCESSIBILITY_URL, IMPRINT_URL, PRIVACY_URL, ROUTES } from "./routes";
import "./index.css";

const onSigninCallback = (user: User | undefined) => {
  // Keycloak returns to "/". The callback params are stripped via the History
  // API; returning to the requested page must go through the router
  // (<ReturnToRequestedPage />), since `replaceState` fires no event.
  const returnTo = (user?.state as { returnTo?: string } | undefined)?.returnTo;
  if (returnTo) rememberReturnTo(returnTo);
  window.history.replaceState({}, document.title, ROUTES.training);
};

/** Once, after a login redirect. */
function ReturnToRequestedPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const target = consumeReturnTo();
    if (target) navigate(target, { replace: true });
  }, [navigate]);

  return null;
}

/** Consent first (ADR 0066), then focus (ADR 0076). */
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

        {/* Above the routes: a transition outlives the screen that started it. */}
        <ScreenTransitionProvider>
          <Routes>
            {/* The first three only forward to the project's pages. */}
            <Route
              path={ROUTES.imprint}
              element={<ProjectPageRedirect title="Impressum" url={IMPRINT_URL} />}
            />
            <Route
              path={ROUTES.privacy}
              element={<ProjectPageRedirect title="Datenschutzerklärung" url={PRIVACY_URL} />}
            />
            <Route
              path={ROUTES.accessibility}
              element={
                <ProjectPageRedirect title="Erklärung zur Barrierefreiheit" url={ACCESSIBILITY_URL} />
              }
            />
            <Route path={ROUTES.notes} element={<Notes />} />

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
                {/* One load for the three dashboard screens, kept mounted across them. */}
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
