import { useEffect, useState, type ReactNode } from "react";

import type { CallState } from "../protocol";
import { cx } from "../utils/cx";
import { formatClock } from "../utils/time";
import CallAnimation from "./CallAnimation";
import ConfirmDialog from "./ConfirmDialog";
import PersonaAvatar from "./PersonaAvatar";

/** A reverse's briefing beside the call (worked from throughout), an ordinary call's facts below. */
export type BriefPlacement = "beside" | "below";

interface CallViewProps {
  personaName: string;
  personaRole: string;
  /** Null after a reload; the initials stand in. */
  personaAvatarUrl: string | null;
  isMicrophoneMuted: boolean;
  callState: CallState;
  audioLevel: number;
  error: string | null;
  onToggleMicrophone: () => void;
  onEndCall: () => void;
  /** A reverse's briefing (ADR 0070) or an ordinary call's facts; one prop, so panel and position agree. */
  brief?: { content: ReactNode; placement: BriefPlacement } | null;
}

/** The live-call screen (F-46). It names no Scenario. The timer counts from mount. */
export default function CallView({
  personaName,
  personaRole,
  personaAvatarUrl,
  isMicrophoneMuted,
  callState,
  audioLevel,
  error,
  onToggleMicrophone,
  onEndCall,
  brief = null,
}: CallViewProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  // Asks first: the call cannot be resumed, and the button sits by the mute toggle.
  const [confirmingEnd, setConfirmingEnd] = useState(false);

  useEffect(() => {
    if (!confirmingEnd) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setConfirmingEnd(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirmingEnd]);

  useEffect(() => {
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const formattedDuration = formatClock(elapsedSeconds);

  return (
    <>
      {/* No Scenario name anywhere, so a random Scenario cannot leak (F-62). */}
      <div
        className={cx(
          "call-layout",
          brief?.placement === "beside" ? "call-layout-with-brief" : null,
        )}
      >
        <section className="call-panel" aria-labelledby="call-persona-name">
          <div className="call-persona">
            <PersonaAvatar
              name={personaName}
              src={personaAvatarUrl}
              className="call-persona-avatar"
            />

            <div className="call-persona-details">
              <h1 id="call-persona-name">{personaName}</h1>
              <p>{personaRole}</p>
            </div>
          </div>

          <p className="call-status">
            <span className="call-status-dot" aria-hidden="true">
              ●
            </span>{" "}
            Gespräch läuft ·{" "}
            <span
              className="call-duration"
              aria-label={`Anrufdauer ${formattedDuration}`}
            >
              {formattedDuration}
            </span>
          </p>

          <CallAnimation state={callState} audioLevel={audioLevel} />

          {error && (
            <p id="status" className="error">
              {error}
            </p>
          )}

          <div className="call-controls">
            <button
              className={cx("mute-call-button", isMicrophoneMuted && "is-muted")}
              type="button"
              aria-pressed={isMicrophoneMuted}
              onClick={onToggleMicrophone}
            >
              <svg
                className="mute-call-icon"
                viewBox="0 0 24 24"
                aria-hidden="true"
                focusable="false"
              >
                <path
                  d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M18 11a6 6 0 0 1-12 0M12 17v4M9 21h6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* The slash, so the icon does not rely on colour. */}
                {isMicrophoneMuted && (
                  <path
                    className="mute-call-icon-slash"
                    d="M4 4 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                )}
              </svg>

              <span>
                {isMicrophoneMuted
                  ? "Mikrofon einschalten"
                  : "Mikrofon stummschalten"}
              </span>
            </button>

            <button
              className="end-call-button"
              type="button"
              onClick={() => setConfirmingEnd(true)}
            >
              Gespräch beenden
            </button>
          </div>
        </section>

        {brief?.content}
      </div>

      {confirmingEnd && (
        <div className="call-confirm-scrim">
          <ConfirmDialog
            title="Gespräch wirklich beenden?"
            body="Das Gespräch wird beendet und ausgewertet."
            cancelLabel="Gespräch fortsetzen"
            confirmLabel="Gespräch beenden"
            destructive
            onCancel={() => setConfirmingEnd(false)}
            // Closed first: a socket that never answers would keep it open forever.
            onConfirm={() => {
              setConfirmingEnd(false);
              onEndCall();
            }}
          />
        </div>
      )}
    </>
  );
}
