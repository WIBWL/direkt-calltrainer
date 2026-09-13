import type { CSSProperties } from "react";

/**
 * The die thrown between the microphone check and a random Scenario's call
 * (F-62).
 *
 * Theatre, and deliberately so: the Scenario was drawn the moment the User
 * committed to the call, because the connection and the Persona's opening line
 * are already being prepared while the microphone check is on screen
 * (ADR 0042) — the case has to be settled before any of that starts. What this
 * screen adds is the *moment* of it. A draw that happens silently between two
 * button presses is a draw the User has no reason to believe in.
 *
 * The number it lands on means nothing and is never read: there are seventeen
 * Scenarios and six faces. It is a die, not a result.
 */

/** Each face by the pips it fills, numbered 1-9 across a three-by-three grid.
 * Front comes first, and the throw ends square on it — so the six is the face
 * it settles on, which is the one worth landing. */
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
    // The throw's length comes from the caller, which is also what times the
    // screen: two numbers that must agree, kept as one.
    <div
      className="dice-stage"
      style={{ "--roll-ms": `${durationMs}ms` } as CSSProperties}
      aria-hidden="true"
    >
      <div className="dice">
        {FACES.map((pips, i) => (
          <div key={SIDES[i]} className={`dice-face dice-face-${SIDES[i]}`}>
            {/* All nine slots always exist: the pips are placed by the grid,
                so a face is a set of filled positions rather than a layout of
                its own. */}
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
