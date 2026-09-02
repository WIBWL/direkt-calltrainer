import { useEffect, useState } from "react";

import { useMicrophoneLevel } from "../hooks/useMicrophoneLevel";
import SetupSection from "./SetupSection";

const HEARD_THRESHOLD = 0.02;

interface MicCheckProps {
  onConfirmed: () => void;
  onCancel: () => void;
}

/** Pre-call microphone test: lets the user confirm that recording works before a session starts. */
export default function MicCheck({ onConfirmed, onCancel }: MicCheckProps) {
  const { level, error, deviceLabel, start, stop } = useMicrophoneLevel();

  // The microphone remains inactive until the user deliberately starts the test.
  const [isTesting, setIsTesting] = useState(false);

  // Keep the successful result once audio has crossed the threshold.
  const [heardSomething, setHeardSomething] = useState(false);

  // Scale the small RMS input range to a percentage for visual and accessible feedback.
  const meterPercentage = Math.min(Math.round(level * 400), 100);

  useEffect(() => {
    if (heardSomething || level < HEARD_THRESHOLD) return;

    // Recording is no longer needed after the microphone has been confirmed.
    setHeardSomething(true);
    stop();
  }, [heardSomething, level, stop]);

  // The same user-triggered handler starts the initial test and any later retry.
  const handleStartTest = async () => {
    setHeardSomething(false);
    setIsTesting(true);
    await start();
  };

  return (
    <>
      <section
        className="setup-intro mic-check-intro"
        aria-labelledby="mic-check-page-title"
      >
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

        {!isTesting && (
          <div className="mic-test-panel">
            <p className="mic-check-hint">
              Starten Sie den Test und sprechen Sie anschließend ein paar Worte.
            </p>

            <button
              className="start-call-button"
              type="button"
              onClick={() => void handleStartTest()}
            >
              Test starten
            </button>
          </div>
        )}

        {isTesting && !heardSomething && (
          <div className="mic-test-panel">
            <p className="mic-check-hint">
              Sagen Sie ein paar Worte, um Ihr Mikrofon zu testen.
            </p>

            <div
              className="mic-meter"
              role="progressbar"
              aria-label="Mikrofonpegel"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={meterPercentage}
            >
              <div
                className="mic-meter-fill"
                style={{ width: `${meterPercentage}%` }}
              />
            </div>

            {error && (
              <p className="error" role="alert">
                Mikrofonzugriff fehlgeschlagen: {error}
              </p>
            )}

            {!error && (
              <p className="mic-test-status" role="status" aria-live="polite">
                Warte auf Audiosignal …
              </p>
            )}
          </div>
        )}

        {heardSomething && (
          <div className="mic-test-panel mic-test-panel-success">
            <div
              className="mic-test-result"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              <span className="mic-test-success-icon" aria-hidden="true">
                ✓
              </span>

              <div className="mic-test-result-copy">
                <h3>Mikrofon funktioniert</h3>
                <p>
                  Ihr Mikrofon wurde erkannt. Sie können das Gespräch jetzt starten.
                </p>
              </div>
            </div>

            <div className="mic-test-actions">
              <button
                className="mic-test-retry-button"
                type="button"
                onClick={() => void handleStartTest()}
              >
                Erneut testen
              </button>

              <button
                className="start-call-button"
                type="button"
                onClick={onConfirmed}
              >
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