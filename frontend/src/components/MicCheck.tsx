import { useEffect, useState } from "react";

import { useMicrophoneLevel } from "../hooks/useMicrophoneLevel";

const HEARD_THRESHOLD = 0.02;

interface MicCheckProps {
  onConfirmed: () => void;
  onCancel: () => void;
}

/** Pre-call microphone test: lets the user see their mic actually picking up
 * audio before a Session starts, rather than discovering a broken mic mid-call. */
export default function MicCheck({ onConfirmed, onCancel }: MicCheckProps) {
  const { level, error, start, stop } = useMicrophoneLevel();
  // Latched, not live: once we've heard *anything* above threshold, stay
  // confirmed — otherwise the button would only be enabled in the exact
  // instant the user happens to still be making sound.
  const [heardSomething, setHeardSomething] = useState(false);

  useEffect(() => {
    void start();
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- start/stop only need to run once, on mount/unmount
  }, []);

  useEffect(() => {
    if (level >= HEARD_THRESHOLD) setHeardSomething(true);
  }, [level]);

  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Mikrofon testen</h1>
      <p className="mic-check-hint">Sag ein paar Worte, um dein Mikrofon zu testen.</p>

      <div className="mic-meter">
        <div className="mic-meter-fill" style={{ width: `${Math.min(level * 400, 100)}%` }} />
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

      <button className="start-call-button" type="button" disabled={!heardSomething} onClick={onConfirmed}>
        Anruf starten
      </button>
      <button className="cancel-button" type="button" onClick={onCancel}>
        Abbrechen
      </button>
    </>
  );
}
