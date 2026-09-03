import type { CallState } from "../protocol";

const LABELS: Record<CallState, string> = {
  listening: "Du bist am Zug",
  thinking: "Persona denkt nach",
  speaking: "Persona spricht",
};

// Maximum heights of the five waveform bars when the persona audio reaches
// its highest measured amplitude.
const WAVE_BAR_MAX_HEIGHTS = [10, 16, 24, 16, 10] as const;

// Keeps the waveform visible as a flat indicator while no persona audio plays.
const MIN_BAR_HEIGHT = 4;

/**
 * Pure state indicator for the live call — no transcript text, ever (ADR 0014
 * extended to cover live text, not just live behavioral feedback).
 */
export default function CallAnimation({
  state,
  audioLevel,
}: {
  state: CallState;
  // Normalized 0..1 amplitude of the currently playing persona TTS audio.
  audioLevel: number;
}) {
  // Only persona speech may animate the waveform. Listening and thinking
  // states remain flat even if a stale audio level were ever received.
  const visibleLevel =
    state === "speaking" ? Math.max(0, Math.min(1, audioLevel)) : 0;

  return (
    <div
      className={`call-animation call-animation-${state}`}
      role="status"
      aria-live="polite"
    >
      <div className="call-wave" aria-hidden="true">
        {WAVE_BAR_MAX_HEIGHTS.map((maxHeight, index) => {
          // Scale each bar between its idle height and individual maximum
          // according to the actual amplitude of the persona audio.
          const height =
            MIN_BAR_HEIGHT + visibleLevel * (maxHeight - MIN_BAR_HEIGHT);

          return (
            <span
              key={`${maxHeight}-${index}`}
              className="call-wave-bar"
              style={{ height: `${height}px` }}
            />
          );
        })}
      </div>

      <p className="call-state-label">{LABELS[state]}</p>
    </div>
  );
}