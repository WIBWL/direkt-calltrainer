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
  const { level, error, start } = useMicrophoneLevel();

  // The microphone remains inactive until the user deliberately starts the test.
  const [isTesting, setIsTesting] = useState(false);

  // Keep the successful result once audio has crossed the threshold.
  const [heardSomething, setHeardSomething] = useState(false);

  useEffect(() => {
    if (level >= HEARD_THRESHOLD) setHeardSomething(true);
  }, [level]);

  // Starting from a user action makes the browser permission request predictable.
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

        {isTesting && (
          <div className="mic-test-panel">
            <p className="mic-check-hint">
              Sagen Sie ein paar Worte, um Ihr Mikrofon zu testen.
            </p>

            <div className="mic-meter">
              <div
                className="mic-meter-fill"
                style={{ width: `${Math.min(level * 400, 100)}%` }}
              />
            </div>

            {error && (
              <p id="status" className="error">
                Mikrofonzugriff fehlgeschlagen: {error}
              </p>
            )}

            {!error && (
              <p id="status" className={heardSomething ? "success" : ""}>
                {heardSomething ? "Mikrofon erkannt." : "Warte auf Audiosignal …"}
              </p>
            )}

            <button
              className="start-call-button"
              type="button"
              disabled={!heardSomething}
              onClick={onConfirmed}
            >
              Anruf starten
            </button>
          </div>
        )}

        <button className="cancel-button" type="button" onClick={onCancel}>
          Abbrechen
        </button>
      </SetupSection>
    </>
  );
}