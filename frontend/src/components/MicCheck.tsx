import { useEffect, useState } from "react";

import { useMicrophoneLevel } from "../hooks/useMicrophoneLevel";
import SetupSection from "./SetupSection";

const HEARD_THRESHOLD = 0.02;

/** The states of the test, as one value: the pairs of booleans this replaces
 * could express combinations that never exist ("passed but not started"), and
 * every panel below had to spell out which pair it meant. "failed" is a state
 * of its own because a microphone that never opened has no level to wait for —
 * without it the running panel waits forever. */
type TestPhase = "idle" | "running" | "failed" | "passed";

interface MicCheckProps {
  onConfirmed: () => void;
  onCancel: () => void;
}

/** Pre-call microphone test: lets the user confirm that recording works before a session starts. */
export default function MicCheck({ onConfirmed, onCancel }: MicCheckProps) {
  const { level, error, deviceLabel, start, stop } = useMicrophoneLevel();

  // The microphone stays inactive until the user deliberately starts the test.
  const [phase, setPhase] = useState<TestPhase>("idle");

  // Scale the small RMS input range to a percentage for visual and accessible feedback.
  const meterPercentage = Math.min(Math.round(level * 400), 100);

  useEffect(() => {
    if (phase !== "running" || level < HEARD_THRESHOLD) return;

    // Recording is no longer needed after the microphone has been confirmed.
    setPhase("passed");
    stop();
  }, [phase, level, stop]);

  // The same user-triggered handler starts the initial test and any later retry.
  const startTest = async () => {
    setPhase("running");
    if (!(await start())) setPhase("failed");
  };

  return (
    <>
      <section className="setup-intro mic-check-intro" aria-labelledby="mic-check-page-title">
        <div className="eyebrow">Mikrofon vorbereiten</div>

        <h1 id="mic-check-page-title">Mikrofon testen</h1>

        <p className="setup-intro-description">
          Prüfen Sie vor dem Gespräch, ob Ihr Mikrofon erkannt wird und Ihre Stimme
          verständlich ankommt.
        </p>
      </section>

      <SetupSection
        index="01"
        title="Mikrofon prüfen"
        description="Sprechen Sie nach dem Start einen kurzen Testsatz."
      >
        {/* This field reports the active device without suggesting unsupported device selection. */}
        <dl className="mic-device-information">
          <div className="mic-device-information-row">
            <dt>Mikrofon</dt>
            <dd>{deviceLabel || "Standardmikrofon"}</dd>
          </div>
        </dl>

        {phase === "idle" && (
          <div className="mic-test-panel">
            <div className="mic-test-panel-copy">
              <h3>Bereit für den Mikrofontest</h3>
              <p className="mic-check-hint">
                Klicken Sie auf „Test starten“ und sprechen Sie einen kurzen Satz.
              </p>
            </div>

            <button className="start-call-button" type="button" onClick={() => void startTest()}>
              Test starten
            </button>
          </div>
        )}

        {phase === "running" && (
          <div className="mic-test-panel">
            <div className="mic-test-panel-copy">
              <h3>Mikrofontest läuft</h3>
              <p className="mic-check-hint">
                Sagen Sie ein paar Worte, um Ihr Mikrofon zu testen.
              </p>
            </div>

            <div
              className="mic-meter"
              role="progressbar"
              aria-label="Mikrofonpegel"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={meterPercentage}
            >
              <div className="mic-meter-fill" style={{ width: `${meterPercentage}%` }} />
            </div>

            <p className="mic-test-status" role="status" aria-live="polite">
              Warte auf Audiosignal …
            </p>
          </div>
        )}

        {phase === "failed" && (
          <div className="mic-test-panel">
            <div className="mic-test-panel-copy">
              <h3>Mikrofon nicht verfügbar</h3>

              <p className="error" role="alert">
                Mikrofonzugriff fehlgeschlagen: {error}
              </p>

              <p className="mic-check-hint">
                Erlauben Sie den Zugriff in Ihrem Browser und starten Sie den Test erneut.
              </p>
            </div>

            <button className="start-call-button" type="button" onClick={() => void startTest()}>
              Erneut testen
            </button>
          </div>
        )}

        {phase === "passed" && (
          <div className="mic-test-panel mic-test-panel-success">
            <div className="mic-test-result" role="status" aria-live="polite" aria-atomic="true">
              <span className="mic-test-success-icon" aria-hidden="true">
                ✓
              </span>

              <div className="mic-test-result-copy">
                <h3>Mikrofon funktioniert</h3>
                <p>Ihre Stimme wurde erkannt. Sie können das Gespräch jetzt starten.</p>
              </div>
            </div>

            <div className="mic-test-actions">
              <button
                className="mic-test-retry-button"
                type="button"
                onClick={() => void startTest()}
              >
                Erneut testen
              </button>

              <button className="start-call-button" type="button" onClick={onConfirmed}>
                Gespräch starten
              </button>
            </div>
          </div>
        )}

        <button className="cancel-button" type="button" onClick={onCancel}>
          Abbrechen
        </button>
      </SetupSection>
    </>
  );
}
