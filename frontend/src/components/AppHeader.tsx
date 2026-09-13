import { useEffect, useId, useRef, useState } from "react";
import { useAuth } from "react-oidc-context";
import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import { cx } from "../utils/cx";
import { useAccount } from "../hooks/useAccount";
import BrandName from "./BrandName";

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
  /** Marks the account chip and its Profil entry as the current page. */
  accountActive?: boolean | undefined;
  /** Marks the account chip and its Fortschritt entry as the current page (F-13). */
  progressActive?: boolean | undefined;
  /**
   * Resets the training flow when the brand is clicked. Every training screen
   * lives under the one route, so from the feedback screen the brand's link
   * points at the path already on display: the router renders nothing new and
   * the click does nothing at all. The screens that are a state rather than a
   * route hand the reset in here; everywhere else the plain link is right.
   */
  onHome?: (() => void) | undefined;
}

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
      <div className="app-header-inner">
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
              <span className="account-chip-caret" />
            </span>
          ) : (
            <AccountMenu
              initials={account.initials}
              displayName={account.displayName}
              accountActive={accountActive}
              progressActive={progressActive}
              onSignOut={() => void auth.signoutRedirect()}
            />
          ))}
      </div>
    </header>
  );
}

interface AccountMenuProps {
  initials: string;
  displayName: string;
  accountActive: boolean;
  progressActive: boolean;
  onSignOut: () => void;
}

/**
 * The account chip and the short list it opens: Profil, Fortschritt, Abmelden.
 *
 * A disclosure, not an ARIA `menu`: the entries are ordinary links and one
 * button, reached with Tab like any others, and `role="menu"` would promise the
 * arrow-key handling a menu bar has and this list does not need.
 */
function AccountMenu({
  initials,
  displayName,
  accountActive,
  progressActive,
  onSignOut,
}: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return undefined;

    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    // Tabbing past the last entry leaves the list open behind the focus
    // otherwise, covering whatever the focus has moved on to.
    const onFocusOut = (event: FocusEvent) => {
      if (!rootRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
    };

    const root = rootRef.current;
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    root?.addEventListener("focusout", onFocusOut);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
      root?.removeEventListener("focusout", onFocusOut);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div className="account-menu" ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className={cx(
          "account-chip",
          (accountActive || progressActive) && "is-active",
          open && "is-open",
        )}
        aria-expanded={open}
        aria-controls={listId}
        // The name is hidden on a narrow screen, and the avatar is decorative.
        aria-label={`Kontomenü für ${displayName}`}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="account-avatar" aria-hidden="true">
          {initials}
        </span>
        <span className="account-chip-name">{displayName}</span>
        <svg className="account-chip-caret" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      </button>

      <ul id={listId} className="account-menu-list" hidden={!open}>
        <li>
          <Link
            to={ROUTES.profile}
            className={cx("account-menu-item", accountActive && "is-active")}
            aria-current={accountActive ? "page" : undefined}
            onClick={close}
          >
            Profil
          </Link>
        </li>
        <li>
          <Link
            to={ROUTES.progress}
            className={cx("account-menu-item", progressActive && "is-active")}
            aria-current={progressActive ? "page" : undefined}
            onClick={close}
          >
            Fortschritt
          </Link>
        </li>
        <li className="account-menu-separator" aria-hidden="true" />
        <li>
          <button type="button" className="account-menu-item" onClick={onSignOut}>
            Abmelden
          </button>
        </li>
      </ul>
    </div>
  );
}
