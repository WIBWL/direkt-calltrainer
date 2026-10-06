import type { CallState } from "../protocol";

const WAVE_BAR_MAX_HEIGHTS = [10, 16, 24, 16, 10] as const;

const MIN_BAR_HEIGHT = 4;

/** A state indicator only: no transcript (ADR 0014), entirely `aria-hidden`. */
export default function CallAnimation({
  state,
  audioLevel,
}: {
  state: CallState;
  audioLevel: number;
}) {
  // Only Persona speech animates the bars.
  const visibleLevel =
    state === "speaking" ? Math.max(0, Math.min(1, audioLevel)) : 0;

  return (
    <div className={`call-animation call-animation-${state}`} aria-hidden="true">
      <div className="call-wave">
        {WAVE_BAR_MAX_HEIGHTS.map((maxHeight, index) => {
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
