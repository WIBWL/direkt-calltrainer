import { useEffect, useState } from "react";

import type { CallState } from "../protocol";
import { cx } from "../utils/cx";
import { formatClock } from "../utils/time";
import CallAnimation from "./CallAnimation";
import PersonaAvatar from "./PersonaAvatar";

interface CallViewProps {
  scenarioName: string;
  personaName: string;
  personaRole: string;
  /** The Persona's portrait. Null after a reload, where the selection is gone
   * and only the stored name is left — the initials stand in then. */
  personaAvatarUrl: string | null;
  languageLabel: string;
  isMicrophoneMuted: boolean;
  callState: CallState;
  audioLevel: number;
  error: string | null;
  onToggleMicrophone: () => void;
  onEndCall: () => void;
}

/**
 * Presentational: the live-call screen (F-46 — mic status via the animation,
 * call duration, and the end-call button). The Session itself is owned and kept
 * alive at the App level (see App.tsx) so it can be pre-warmed before this
 * screen ever mounts — so the timer counts from mount, not from Session start,
 * which is close enough given pre-warm is at most a few seconds.
 */
export default function CallView({
  scenarioName,
  personaName,
  personaRole,
  personaAvatarUrl,
  languageLabel,
  isMicrophoneMuted,
  callState,
  audioLevel,
  error,
  onToggleMicrophone,
  onEndCall,
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
      <section className="setup-intro call-intro" aria-labelledby="call-page-title">
        <div className="eyebrow">Gespräch läuft</div>

        <h1 id="call-page-title">{scenarioName}</h1>

        <p className="setup-intro-description">
          Gespräch mit {personaName} · {languageLabel}
        </p>
      </section>

      <section className="call-panel" aria-labelledby="call-persona-name">
        <div className="call-persona">
          <PersonaAvatar
            name={personaName}
            src={personaAvatarUrl}
            className="call-persona-avatar"
          />

          <div className="call-persona-details">
            <h2 id="call-persona-name">{personaName}</h2>
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
    </>
  );
}
