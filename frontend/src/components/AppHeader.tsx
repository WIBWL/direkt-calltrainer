import { useAuth } from "react-oidc-context";
import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import { cx } from "../utils/cx";
import { useAccount } from "../hooks/useAccount";
import BrandName from "./BrandName";

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
  /** Marks the progress link as the current page (F-13). */
  progressActive?: boolean | undefined;
  /** Widens the header bar to a wide page's measure, so the two align. */
  wide?: boolean | undefined;
  /**
   * Resets the training flow when the brand is clicked. Every training screen
   * lives under the one route, so from the feedback screen the brand's link
   * points at the path already on display: the router renders nothing new and
   * the click does nothing at all. The screens that are a state rather than a
   * route hand the reset in here; everywhere else the plain link is right.
   */
  onHome?: (() => void) | undefined;
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
  progressActive = false,
  wide = false,
  onHome,
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

      <span className="app-brand-name">
        <BrandName />
      </span>
    </div>
  );

  return (
    <header className="app-header">
      <div className={cx("app-header-inner", wide && "is-wide")}>
        {navigationLocked ? (
          brand
        ) : (
          <Link
            to={ROUTES.training}
            className="app-brand-link"
            aria-label="Zum Training"
            onClick={onHome}
            // The reset is the whole of the navigation where `onHome` is set,
            // and the route does not change: pushing the path a second time
            // would leave a history entry that goes nowhere.
            replace={Boolean(onHome)}
          >
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

        {/* Suppressed during a call for the same reason the account chip is:
            leaving the page tears the WebSocket down (ADR 0034). */}
        {auth.isAuthenticated && !navigationLocked && (
          <Link
            to={ROUTES.progress}
            className={cx("header-link", progressActive && "is-active")}
            aria-current={progressActive ? "page" : undefined}
          >
            Fortschritt
          </Link>
        )}

        {auth.isAuthenticated &&
          (navigationLocked ? (
            // Hidden, not greyed out: during the microphone check and the call
            // the chip has nothing to offer, and a dimmed control still invites
            // the click it is refusing. It carries the full content anyway so
            // that it reserves the same width the real chip has -- otherwise
            // the progress steps shift sideways on entering the call.
            <span className="account-chip is-locked" aria-hidden="true">
              <span className="account-avatar">{account.initials}</span>
              <span className="account-chip-name">{account.displayName}</span>
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
