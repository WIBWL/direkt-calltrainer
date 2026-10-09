import type { CSSProperties } from "react";

/** The die before a random Scenario's call (F-66). Theatre: the Scenario was drawn at commit (ADR 0042). */

/** Pips by slot, 1-9 across a 3x3 grid. Front first: the throw lands on it. */
const FACES: number[][] = [
  [1, 3, 4, 6, 7, 9], // front, the one it lands on
  [1, 5, 9], // back
  [3, 7], // right
  [1, 3, 7, 9], // left
  [5], // top
  [1, 3, 5, 7, 9], // bottom
];

const SIDES = ["front", "back", "right", "left", "top", "bottom"];

export default function DiceRoll({ durationMs }: { durationMs: number }) {
  return (
    // The caller's length also times the screen.
    <div
      className="dice-stage"
      style={{ "--roll-ms": `${durationMs}ms` } as CSSProperties}
      aria-hidden="true"
    >
      <div className="dice">
        {FACES.map((pips, i) => (
          <div key={SIDES[i]} className={`dice-face dice-face-${SIDES[i]}`}>
            {Array.from({ length: 9 }, (_, slot) => (
              <span
                key={slot}
                className={pips.includes(slot + 1) ? "dice-pip" : "dice-pip is-empty"}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="dice-shadow" />
    </div>
  );
}
