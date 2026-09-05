import type { CallState } from "../protocol";

// Maximum heights of the five waveform bars when the persona audio reaches
// its highest measured amplitude.
const WAVE_BAR_MAX_HEIGHTS = [10, 16, 24, 16, 10] as const;

// Keeps the waveform visible as a flat indicator while no persona audio plays.
const MIN_BAR_HEIGHT = 4;

/**
 * Pure state indicator for the live call — no transcript text, ever (ADR 0014
 * extended to cover live text, not just live behavioral feedback), and no
 * spoken phase announcement for a screen reader either: a real phone call
 * gives a blind caller no narrated "listening/thinking/speaking" either, just
 * the other person's voice and the gaps around it, which the persona's actual
 * audio already provides. Entirely `aria-hidden`, so nothing here talks over
 * the call itself.
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
    <div className={`call-animation call-animation-${state}`} aria-hidden="true">
      <div className="call-wave">
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
    </div>
  );
}
