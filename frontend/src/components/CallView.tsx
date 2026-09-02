import { useEffect, useState } from "react";

import type { CallState } from "../protocol";
import CallAnimation from "./CallAnimation";

interface CallViewProps {
  scenarioName: string;
  personaName: string;
  languageLabel: string;
  callState: CallState;
  error: string | null;
  onEndCall: () => void;
}

/** mm:ss for a non-negative second count. */
function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
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
  languageLabel,
  callState,
  error,
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

      <CallAnimation state={callState} />

      <p className="call-duration" aria-label="Anrufdauer">
        {formatDuration(elapsedSeconds)}
      </p>

      {error && (
        <p id="status" className="error">
          {error}
        </p>
      )}

      <button className="end-call-button" type="button" onClick={onEndCall}>
        Anruf beenden
      </button>
    </>
  );
}
