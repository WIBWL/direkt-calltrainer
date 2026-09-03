import { useEffect, useState } from "react";

import type { CallState } from "../protocol";
import CallAnimation from "./CallAnimation";

interface CallViewProps {
  scenarioName: string;
  personaName: string;
  personaRole: string;
  languageLabel: string;
  isMicrophoneMuted: boolean;
  callState: CallState;
  audioLevel: number;
  error: string | null;
  onToggleMicrophone: () => void;
  onEndCall: () => void;
}

/** mm:ss for a non-negative second count. */
function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** Initials for the persona avatar, limited to the first two name parts. */
function getInitials(name: string): string {
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  return initials || "?";
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

  const formattedDuration = formatDuration(elapsedSeconds);

  return (
    <>
      <section
        className="setup-intro call-intro"
        aria-labelledby="call-page-title"
      >
        <div className="eyebrow">Gespräch läuft</div>

        <h1 id="call-page-title">{scenarioName}</h1>

        <p className="setup-intro-description">
          Gespräch mit {personaName} · {languageLabel}
        </p>
      </section>

      <section className="call-panel" aria-labelledby="call-persona-name">
        <div className="call-persona">
          <div className="call-persona-avatar" aria-hidden="true">
            {getInitials(personaName)}
          </div>

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
            className={
              "mute-call-button" + (isMicrophoneMuted ? " is-muted" : "")
            }
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
