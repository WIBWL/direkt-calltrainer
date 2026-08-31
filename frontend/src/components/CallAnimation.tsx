import type { CallState } from "../protocol";

const LABELS: Record<CallState, string> = {
  listening: "Du bist am Zug",
  thinking: "Persona denkt nach",
  speaking: "Persona spricht",
};

/**
 * Pure state indicator for the live call — no transcript text, ever (ADR 0014
 * extended to cover live text, not just live behavioral feedback).
 */
export default function CallAnimation({ state }: { state: CallState }) {
  return (
    <div className="call-animation" aria-live="polite">
      <div className={`call-orb call-orb-${state}`} aria-hidden="true" />
      <p className="call-state-label">{LABELS[state]}</p>
    </div>
  );
}
