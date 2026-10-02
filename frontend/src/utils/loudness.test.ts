import { describe, expect, it } from "vitest";

import {
  describeLoudness,
  loudnessClock,
  loudnessRuns,
  type LoudnessCurve,
} from "./loudness";

/**
 * The drawing arithmetic of F-37's loudness course (the reading is the server's,
 * ADR 0091). A bridge one point too long draws a line across a silence,
 * asserting a level nobody spoke at, and looks perfectly ordinary.
 */

describe("loudnessRuns", () => {
  it("returns one run for an unbroken curve", () => {
    expect(loudnessRuns([1, 2, 3])).toEqual([[0, 1, 2]]);
  });

  it("draws through a breathing pause rather than breaking at it", () => {
    const smoothed = [1, 2, null, null, 3, 4];

    expect(loudnessRuns(smoothed)).toEqual([[0, 1, 4, 5]]);
  });

  it("bridges a gap of exactly twenty points, the longest it may", () => {
    const smoothed = [1, ...Array<null>(20).fill(null), 2];

    expect(loudnessRuns(smoothed)).toEqual([[0, 21]]);
  });

  it("breaks the run at twenty-one, where the silence stops being a pause", () => {
    const smoothed = [1, 2, ...Array<null>(21).fill(null), 3, 4];

    expect(loudnessRuns(smoothed)).toEqual([
      [0, 1],
      [23, 24],
    ]);
  });

  it("drops a run of one point, because a line needs two", () => {
    const smoothed = [1, ...Array<null>(21).fill(null), 2];

    expect(loudnessRuns(smoothed)).toEqual([]);
  });

  it("ignores leading and trailing silence", () => {
    const smoothed = [null, null, 1, 2, null, null];

    expect(loudnessRuns(smoothed)).toEqual([[2, 3]]);
  });

  it("finds nothing in a curve that measured nothing", () => {
    expect(loudnessRuns([])).toEqual([]);
    expect(loudnessRuns([null, null])).toEqual([]);
  });
});

describe("loudnessClock", () => {
  it("reads an index on the user's own speaking clock at 100 ms a point", () => {
    expect(loudnessClock(0)).toBe("0:00");
    expect(loudnessClock(10)).toBe("0:01");
    expect(loudnessClock(600)).toBe("1:00");
  });
});

describe("describeLoudness", () => {
  const curve = (stretches: LoudnessCurve["stretches"]): LoudnessCurve =>
    ({ stretches, total: "2:30" } as LoudnessCurve);

  it("says so plainly when nothing left the band", () => {
    expect(describeLoudness(curve([]))).toBe(
      "Lautstärkeverlauf über 2:30 Sprechzeit: durchgehend im gewohnten Bereich, " +
        "ohne längere Abweichung.",
    );
  });

  it("names the direction of one departure", () => {
    const text = describeLoudness(curve([{ direction: "quieter", peakIndex: 4 }]));

    expect(text).toBe("Lautstärkeverlauf über 2:30 Sprechzeit: leiser an einer Stelle.");
  });

  it("names both directions when there are two", () => {
    const text = describeLoudness(
      curve([
        { direction: "louder", peakIndex: 2 },
        { direction: "quieter", peakIndex: 9 },
      ]),
    );

    expect(text).toContain("lauter an einer Stelle, leiser an einer Stelle");
  });

  it("never reads as a judgement, only as a location", () => {
    const text = describeLoudness(curve([{ direction: "louder", peakIndex: 1 }]));

    // ADR 0004/0051: the course carries no target, so the sentence under it
    // may say where the line went and not whether that was good.
    expect(text).not.toMatch(/zu laut|zu leise|besser|schlecht|gut/i);
  });
});
