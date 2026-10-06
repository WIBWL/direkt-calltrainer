import { useEffect, useRef, useState } from "react";

import type { MicDevice } from "../hooks/useMicrophoneDevices";
import { useMicrophoneLevel } from "../hooks/useMicrophoneLevel";

const HEARD_THRESHOLD = 0.02;
const REQUIRED_HEARD_DURATION_MS = 450;

/** One value, so impossible pairs cannot arise; "failed" has no level to wait for. */
type TestPhase = "idle" | "starting" | "running" | "failed" | "passed";

interface MicCheckProps {
  deviceId: string | null;
  devices: MicDevice[];
  onDeviceChange: (deviceId: string | null) => void;
  /** Labels are empty until permission is granted once. */
  onDevicesRefresh: () => void;
  onConfirmed: () => void;
  onCancel: () => void;
  /** The button names the step it actually takes. */
  briefingFollows: boolean;
}

/** Pick a device and confirm recording works before the call. */
export default function MicCheck({
  deviceId,
  devices,
  onDeviceChange,
  onDevicesRefresh,
  onConfirmed,
  onCancel,
  briefingFollows,
}: MicCheckProps) {
  const { level, error, start, stop } = useMicrophoneLevel(deviceId);

  const [phase, setPhase] = useState<TestPhase>("idle");
  const heardDurationRef = useRef(0);
  const lastLevelTimestampRef = useRef<number | null>(null);

  const meterPercentage = Math.min(Math.round(level * 400), 100);

  useEffect(() => {
    if (phase !== "running") {
      lastLevelTimestampRef.current = null;
      return;
    }

    const now = performance.now();
    const previousTimestamp = lastLevelTimestampRef.current;
    lastLevelTimestampRef.current = now;

    if (level >= HEARD_THRESHOLD && previousTimestamp !== null) {
      heardDurationRef.current += Math.min(now - previousTimestamp, 100);
    }

    if (heardDurationRef.current < REQUIRED_HEARD_DURATION_MS) return;

    setPhase("passed");
    stop();
  }, [phase, level, stop]);

  const startTest = async () => {
    heardDurationRef.current = 0;
    lastLevelTimestampRef.current = null;
    setPhase("starting");

    const opened = await start();
    if (opened === null) return; // a device change restarted the test meanwhile
    if (opened) {
      onDevicesRefresh(); // labels are only real once permission was granted
      setPhase("running");
    } else {
      setPhase("failed");
    }
  };

  // A device change restarts a running test.
  useEffect(() => {
    if (phase === "starting" || phase === "running") void startTest();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a deviceId change (not every re-render) should restart the running test
  }, [deviceId]);

  return (
    <>
      <section className="setup-intro mic-check-intro" aria-labelledby="mic-check-page-title">
        <h1 id="mic-check-page-title">Mikrofon testen</h1>

        <p className="setup-intro-description">
          Prüfen Sie vor dem Gespräch, ob Ihr Mikrofon erkannt wird und Ihre Stimme
          verständlich ankommt.
        </p>
      </section>

      <section className="setup-section">
        <label className="mic-device-label" htmlFor="mic-device-select">
          Mikrofon auswählen
        </label>

        <div className="mic-device-information">
          <select
            id="mic-device-select"
            className="mic-device-select"
            value={deviceId ?? ""}
            onChange={(e) => onDeviceChange(e.target.value || null)}
          >
            <option value="">Standardmikrofon</option>
            {devices.map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || `Mikrofon ${index + 1}`}
              </option>
            ))}
          </select>
        </div>

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

        {(phase === "starting" || phase === "running") && (
          <div className="mic-test-panel">
            <div className="mic-test-panel-copy">
              <h3>
                {phase === "starting" ? "Mikrofon wird vorbereitet" : "Mikrofontest läuft"}
              </h3>

              <p className="mic-check-hint">
                {phase === "starting"
                  ? "Das Mikrofon wird initialisiert. Einen Moment bitte."
                  : "Sagen Sie ein paar Worte, um Ihr Mikrofon zu testen."}
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
              {phase === "starting" ? "Mikrofon wird initialisiert …" : "Warte auf Audiosignal …"}
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
                <p>
                  {briefingFollows
                    ? "Ihre Stimme wurde erkannt. Sie erhalten jetzt Ihr Briefing."
                    : "Ihre Stimme wurde erkannt. Sie können das Gespräch jetzt starten."}
                </p>
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
                {briefingFollows ? "Weiter zum Briefing" : "Gespräch starten"}
              </button>
            </div>
          </div>
        )}

      </section>

      <button className="back-to-start-button" type="button" onClick={onCancel}>
        Zurück zur Vorbereitung
      </button>
    </>
  );
}
