import type { CallState } from "../protocol";
import CallAnimation from "./CallAnimation";

interface CallViewProps {
  callState: CallState;
  error: string | null;
  onEndCall: () => void;
}

/** Presentational: the live-call screen. The Session itself is owned and
 * kept alive at the App level (see App.tsx) so it can be pre-warmed before
 * this screen ever mounts. */
export default function CallView({ callState, error, onEndCall }: CallViewProps) {
  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Anruf läuft</h1>

      <CallAnimation state={callState} />

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
