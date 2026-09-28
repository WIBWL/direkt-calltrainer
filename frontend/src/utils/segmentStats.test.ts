import { describe, expect, it } from "vitest";

import { segment, session } from "../test/sessions";
import { pairFor, segmentTrainings } from "./segmentStats";

/** Pairing a call's demanding stretches with the rest (ADR 0081): two figures, no
 * difference, ratio or direction (ADR 0051). Also pins that loudness is dropped
 * across trainings — one `comparableAcrossCalls` call no type would miss. */

/** A training with a pressure/rest pair for each metric named. */
const withPairs = (
  pairs: Record<string, [pressure: number, rest: number]>,
  over: Parameters<typeof session>[0] = {},
) =>
  session({
    segments: Object.entries(pairs).flatMap(([key, [pressure, rest]]) => [
      segment("pressure", key, pressure),
      segment("rest", key, rest),
    ]),
    ...over,
  });

describe("pairing the two stretches", () => {
  it("puts a metric's two figures on one row", () => {
    const [training] = segmentTrainings([withPairs({ pace: [150, 128] })]);

    expect(training?.pairs).toEqual([
      { key: "pace", name: "pace", unit: null, pressure: 150, rest: 128 },
    ]);
  });

  it("keeps a row where only one stretch was long enough to measure", () => {
    // A stretch too short yields no row for that half, and the other still says
    // something on its own.
    const [training] = segmentTrainings([
      session({ segments: [segment("pressure", "pace", 150)] }),
    ]);

    expect(training?.pairs[0]).toMatchObject({ pressure: 150, rest: null });
  });

  it("computes no difference, no ratio and no verdict", () => {
    // The reader draws the comparison. A derived "stability" would be the
    // refused norm wearing a different name, and this is the assertion that
    // notices one being added.
    const [training] = segmentTrainings([withPairs({ pace: [150, 128] })]);

    expect(Object.keys(training?.pairs[0] ?? {}).sort()).toEqual([
      "key",
      "name",
      "pressure",
      "rest",
      "unit",
    ]);
  });
});

describe("which trainings carry a comparison", () => {
  it("leaves out a call in which nobody pushed back", () => {
    // Also every call recorded before the per-utterance facts were kept: the
    // audio is gone (ADR 0048), so those can never gain one.
    expect(segmentTrainings([session({ segments: [] })])).toEqual([]);
  });

  it("keeps the history's order, newest training first", () => {
    const trainings = segmentTrainings([
      withPairs({ pace: [150, 128] }, { session_id: "neu" }),
      withPairs({ pace: [140, 130] }, { session_id: "alt" }),
    ]);

    expect(trainings.map((t) => t.sessionId)).toEqual(["neu", "alt"]);
  });

  it("carries what the row needs to link into its training", () => {
    const [training] = segmentTrainings([
      withPairs({ pace: [150, 128] }, { session_id: "abc", scenario: "Preisgespräch" }),
    ]);

    expect(training).toMatchObject({
      sessionId: "abc",
      scenario: "Preisgespräch",
      persona: "Thomas Brandt",
      at: "2026-09-01T10:00:00Z",
    });
  });
});

describe("the loudness", () => {
  it("is left off the goal's page, where the rows run one training under the next", () => {
    const [training] = segmentTrainings([withPairs({ pace: [150, 128], loudness: [14, 11] })]);
    expect(training?.pairs.map((p) => p.key)).toEqual(["pace"]);
  });

  it("drops a training whose only comparison is the loudness", () => {
    // Otherwise the page would show a row with a heading and nothing under it.
    expect(segmentTrainings([withPairs({ loudness: [14, 11] })])).toEqual([]);
  });

  it("stays on the single call, where the microphone is the same on both sides", () => {
    const call = withPairs({ loudness: [14, 11] });
    expect(pairFor(call.segments, "loudness")).toMatchObject({ pressure: 14, rest: 11 });
  });
});

describe("one metric of one call", () => {
  it("is absent where that call has no pair for it", () => {
    expect(pairFor(withPairs({ pace: [150, 128] }).segments, "pauses")).toBeNull();
  });
});
