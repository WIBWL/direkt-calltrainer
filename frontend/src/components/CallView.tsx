import { useEffect, useState, type ReactNode } from "react";

import type { CallState } from "../protocol";
import { cx } from "../utils/cx";
import { formatClock } from "../utils/time";
import CallAnimation from "./CallAnimation";
import PersonaAvatar from "./PersonaAvatar";

interface CallViewProps {
  personaName: string;
  personaRole: string;
  /** The Persona's portrait. Null after a reload, where the selection is gone
   * and only the stored name is left — the initials stand in then. */
  personaAvatarUrl: string | null;
  isMicrophoneMuted: boolean;
  callState: CallState;
  audioLevel: number;
  error: string | null;
  onToggleMicrophone: () => void;
  onEndCall: () => void;
  /** The reverse briefing (ADR 0070), or null. Passed in rather than fetched
   * here: this screen stays presentational, and the panel is the same one the
   * mic check already showed. */
  brief?: ReactNode;
}

/**
 * Presentational: the live-call screen (F-46 — mic status via the animation,
 * call duration, and the end-call button). One panel and nothing above it:
 * during a call the screen shows who is on the line, and the Scenario's name
 * is neither needed nor wanted there (see the note in the markup). The Session itself is owned and kept
 * alive at the App level (see App.tsx) so it can be pre-warmed before this
 * screen ever mounts — so the timer counts from mount, not from Session start,
 * which is close enough given pre-warm is at most a few seconds.
 */
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
      {/* No heading above the panel, and none of what used to be in it: the
          Scenario's name, the Persona's and the language stood over the call
          as a page title, which is a caption on a phone call. What is on the
          other end of the line is in the panel itself, and it is the only
          thing on this screen. It also means a Zufallsszenario's case cannot
          leak here by construction rather than by a condition (F-62). */}

      {/* One column, or two once there is a briefing to keep in view: reading
          it must not mean scrolling the animation off the screen (ADR 0070). */}
      <div className={cx("call-layout", brief ? "call-layout-with-brief" : null)}>
        <section className="call-panel" aria-labelledby="call-persona-name">
          <div className="call-persona">
            <PersonaAvatar
              name={personaName}
              src={personaAvatarUrl}
              className="call-persona-avatar"
            />

            <div className="call-persona-details">
              {/* The page's heading now that the title above is gone: this
                  screen is about the person on the line. */}
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

          {/* The toggle state reflects whether local VAD microphone capture is paused. */}
          <div className="call-controls">
            <button
              className={cx("mute-call-button", isMicrophoneMuted && "is-muted")}
              type="button"
              aria-pressed={isMicrophoneMuted}
              onClick={onToggleMicrophone}
            >
              {isMicrophoneMuted
                ? "Mikrofon einschalten"
                : "Mikrofon stummschalten"}
            </button>

            <button className="end-call-button" type="button" onClick={onEndCall}>
              Gespräch beenden
            </button>
          </div>
        </section>

        {brief}
      </div>
    </>
  );
}
