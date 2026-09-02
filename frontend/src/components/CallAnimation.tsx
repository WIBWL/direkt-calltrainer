import type { CallState } from "../protocol";

const LABELS: Record<CallState, string> = {
  listening: "Du bist am Zug",
  thinking: "Persona denkt nach",
  speaking: "Persona spricht",
};

// Static bar heights reproduce the compact voice wave from the Figma design.
const WAVE_BAR_HEIGHTS = [8, 8, 16, 24, 8] as const;

/**
 * Pure state indicator for the live call — no transcript text, ever (ADR 0014
 * extended to cover live text, not just live behavioral feedback).
 */
export default function CallAnimation({ state }: { state: CallState }) {
  return (
    <div
      className={`call-animation call-animation-${state}`}
      role="status"
      aria-live="polite"
    >
      <div className="call-wave" aria-hidden="true">
        {WAVE_BAR_HEIGHTS.map((height, index) => (
          <span
            key={`${height}-${index}`}
            className="call-wave-bar"
            style={{ height }}
          />
        ))}
      </div>

      <p className="call-state-label">{LABELS[state]}</p>
    </div>
  );
}