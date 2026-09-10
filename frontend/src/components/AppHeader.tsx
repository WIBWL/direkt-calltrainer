import { useAuth } from "react-oidc-context";
import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import { cx } from "../utils/cx";
import { useAccount } from "../hooks/useAccount";

// The header uses the current screen to highlight the matching training step.
export type TrainingStep = "prepare" | "call" | "feedback";

// `| undefined` is spelled out on each optional prop because the project builds
// with `exactOptionalPropertyTypes`: under it, "may be omitted" and "may be
// passed as undefined" are different types, and AppLayout forwards these
// straight through, which is the second of the two.
interface AppHeaderProps {
  /** Omitted outside the training flow — the profile screen is not a step. */
  activeStep?: TrainingStep | undefined;
  /**
   * Suppresses every link in the header. Set while a call is live: leaving the
   * page tears down the WebSocket, and an abandoned Session is deliberately
   * never persisted (ADR 0034), so a stray click would destroy the recording
   * with no way to get it back.
   */
  navigationLocked?: boolean | undefined;
  /** Marks the account chip as the current page. */
  accountActive?: boolean | undefined;
}

// Keeping the step configuration here avoids duplicating the markup.
const trainingSteps: { id: TrainingStep; label: string }[] = [
  { id: "prepare", label: "Vorbereiten" },
  { id: "call", label: "Gespräch" },
  { id: "feedback", label: "Feedback" },
];

export default function AppHeader({
  activeStep,
  navigationLocked = false,
  accountActive = false,
}: AppHeaderProps) {
  const auth = useAuth();
  const account = useAccount();
  const activeStepIndex = trainingSteps.findIndex((step) => step.id === activeStep);

  const brand = (
    <div className="app-brand">
      <img
        className="app-brand-logo"
        src="/logo.png"
        alt=""
        aria-hidden="true"
      />

      <span className="app-brand-name">Calltrainer</span>
    </div>
  );

  return (
    <header className="app-header">
      <div className="app-header-inner">
        {navigationLocked ? (
          brand
        ) : (
          <Link to={ROUTES.training} className="app-brand-link" aria-label="Zum Training">
            {brand}
          </Link>
        )}

        {activeStep ? (
          <ol className="training-progress" aria-label="Trainingsfortschritt">
            {trainingSteps.map((step, index) => {
              const isActive = step.id === activeStep;
              const isComplete = index < activeStepIndex;

              return (
                <li
                  key={step.id}
                  className={cx(
                    "training-progress-step",
                    isActive && "is-active",
                    isComplete && "is-complete",
                  )}
                  aria-current={isActive ? "step" : undefined}
                >
                  <span className="training-progress-number">{index + 1}</span>
                  <span className="training-progress-label">{step.label}</span>

                  {index < trainingSteps.length - 1 && (
                    <span className="training-progress-connector" aria-hidden="true" />
                  )}
                </li>
              );
            })}
          </ol>
        ) : (
          // Holds the brand left and the account right when there are no steps
          // between them.
          <span className="app-header-spacer" />
        )}

        {auth.isAuthenticated &&
          (navigationLocked ? (
            // Not merely disabled: during a call the chip has nothing to offer,
            // and a greyed-out control invites the click it is refusing.
            <span className="account-chip is-locked" title="Während des Gesprächs nicht verfügbar">
              <span className="account-avatar" aria-hidden="true">
                {account.initials}
              </span>
            </span>
          ) : (
            <Link
              to={ROUTES.profile}
              className={cx("account-chip", accountActive && "is-active")}
              aria-current={accountActive ? "page" : undefined}
            >
              <span className="account-avatar" aria-hidden="true">
                {account.initials}
              </span>
              <span className="account-chip-name">{account.displayName}</span>
            </Link>
          ))}
      </div>
    </header>
  );
}
