import { describe, expect, it } from "vitest";

import { measurement, session } from "../test/sessions";
import {
  activity,
  activityMonth,
  activityStep,
  band,
  callDurationMs,
  completeParts,
  completedOnly,
  dayKey,
  durationSeries,
  firstTrainingMonth,
  formatBand,
  formatPoint,
  halves,
  latest,
  median,
  mostVarying,
  readable,
  selectionSeries,
  toSeries,
  trainingsOn,
  trainingsWith,
  variety,
} from "./progressStats";

/** F-13, ADR 0051/0065: the dashboard's arithmetic, which renders perfectly when wrong. */

describe("building a series from the history", () => {
  it("turns the newest-first history into points oldest first", () => {
    // Newest first in (ADR 0064), oldest first in the chart.
    const series = toSeries([
      session({ started_at: "2026-09-03T10:00:00Z", measurements: [measurement("pace", 3)] }),
      session({ started_at: "2026-09-02T10:00:00Z", measurements: [measurement("pace", 2)] }),
      session({ started_at: "2026-09-01T10:00:00Z", measurements: [measurement("pace", 1)] }),
    ]);

    expect(series).toHaveLength(1);
    expect(series[0]?.points.map((p) => p.value)).toEqual([1, 2, 3]);
  });

  it("leaves out the loudness, which is not comparable between calls", () => {
    // Its dB span measures the microphone across calls (ADR 0076).
    const series = toSeries([
      session({ measurements: [measurement("loudness", 12), measurement("pace", 130)] }),
    ]);

    expect(series.map((s) => s.key)).toEqual(["pace"]);
  });

  it("gives a checklist metric no band, whatever its values", () => {
    // ADR 0086.
    const series = toSeries([
      session({ measurements: [measurement("opening", 3)] }),
      session({ measurements: [measurement("opening", 2)] }),
      session({ measurements: [measurement("opening", 3)] }),
    ]);

    expect(series[0]?.shape).toBe("parts");
    expect(series[0]?.band).toBeNull();
  });

  it("carries the training a point came from, so a chart can link into it", () => {
    const series = toSeries([
      session({
        session_id: "abc",
        scenario: "Preisgespräch",
        persona: "Lena Hoffmann",
        measurements: [measurement("pace", 130)],
      }),
    ]);

    expect(series[0]?.points[0]).toMatchObject({
      sessionId: "abc",
      scenario: "Preisgespräch",
      persona: "Lena Hoffmann",
    });
  });
});

describe("the user's own usual range", () => {
  it("describes nothing below three values", () => {
    expect(band([10, 20])).toBeNull();
  });

  it("is the median widened by the median absolute deviation", () => {
    // The outlier moves the band by nothing.
    expect(band([1, 2, 3, 4, 100])).toEqual({ median: 3, low: 2, high: 4 });
  });

  it("falls back to the mean deviation where more than half the values are equal", () => {
    // MAD 0, but a zero-width band would claim exactly 5 every time.
    const result = band([5, 5, 5, 9]);
    expect(result?.median).toBe(5);
    expect(result?.high).toBeCloseTo(6, 10);
    expect(result?.low).toBeCloseTo(4, 10);
  });

  it("has no width at all where every value is identical", () => {
    // Inventing a width would be the first threshold.
    expect(band([7, 7, 7])).toEqual({ median: 7, low: 7, high: 7 });
  });

  it("takes the mean of the middle two for an even count", () => {
    expect(median([1, 2, 3, 4])).toBe(2.5);
  });
});

describe("writing the range out", () => {
  const counted = (values: number[]) => ({
    ...(toSeries(values.map((v) => session({ measurements: [measurement("interruptions", v, { unit: "Anzahl" })] })))[0]!),
  });

  it("never reaches below zero for a count", () => {
    // Median 0, spread 2: the band would start at -2.
    const series = counted([0, 0, 0, 5, 5]);
    expect(series.band?.low).toBeLessThan(0);
    expect(formatBand(series)).toBe("0 bis 2");
  });

  it("says 'meist N' where both ends round to the same number", () => {
    const series = counted([1, 1, 1, 1]);
    expect(formatBand(series)).toBe("meist 1");
  });

  it("writes a decimal with the German comma and the unit once", () => {
    const series = toSeries([
      session({ measurements: [measurement("reaction_time", 1.2, { unit: "s" })] }),
      session({ measurements: [measurement("reaction_time", 1.8, { unit: "s" })] }),
      session({ measurements: [measurement("reaction_time", 2.4, { unit: "s" })] }),
    ])[0]!;

    expect(formatBand(series)).toBe("1,2 bis 2,4 s");
  });
});

describe("the earlier half and the recent one", () => {
  const paces = (values: number[]) =>
    toSeries(
      [...values]
        .reverse()
        .map((value) => session({ measurements: [measurement("pace", value)] })),
    )[0]!;

  it("describes each half on its own terms", () => {
    const split = halves(paces([10, 10, 10, 20, 20, 20]));

    expect(split).toEqual({
      each: 3,
      early: { median: 10, low: 10, high: 10 },
      late: { median: 20, low: 20, high: 20 },
    });
  });

  it("computes no difference, no ratio and no direction", () => {
    // ADR 0065 rules out a delta.
    const split = halves(paces([10, 10, 10, 20, 20, 20]));

    expect(Object.keys(split ?? {}).sort()).toEqual(["each", "early", "late"]);
  });

  it("leaves the middle training out of an odd count", () => {
    // The odd middle would skew one half or both.
    const split = halves(paces([1, 2, 3, 99, 7, 8, 9]));

    expect(split?.each).toBe(3);
    expect(split?.early.median).toBe(2);
    expect(split?.late.median).toBe(8);
  });

  it("says nothing below twice the series threshold", () => {
    expect(halves(paces([1, 2, 3, 4, 5]))).toBeNull();
    expect(halves(paces([1, 2, 3, 4, 5, 6]))).not.toBeNull();
  });

  it("says nothing for a checklist, which has no band at all", () => {
    const openings = toSeries(
      Array.from({ length: 8 }, () => session({ measurements: [measurement("opening", 3)] })),
    )[0]!;

    expect(halves(openings)).toBeNull();
  });
});

describe("a checklist's figures", () => {
  const openings = (counts: number[]) =>
    toSeries(counts.map((c) => session({ measurements: [measurement("opening", c)] })))[0]!;

  it("reads a value as parts recognised, never as a fraction", () => {
    // F-63.
    expect(formatPoint(openings([2]), 2)).toBe("2 Teile erkannt");
    expect(formatPoint(openings([1]), 1)).toBe("1 Teil erkannt");
  });

  it("counts the trainings in which every part was there", () => {
    expect(completeParts(openings([2, 3, 3]))).toBe(2);
  });

  it("has nothing to count for an ordinary metric", () => {
    const pace = toSeries([session({ measurements: [measurement("pace", 130)] })])[0]!;
    expect(completeParts(pace)).toBeNull();
  });
});

describe("selecting trainings", () => {
  const five = [session(), session(), session(), session(), session()];

  it("takes the most recent, which is the front of the list", () => {
    expect(latest(five, 2)).toEqual([five[0], five[1]]);
  });

  it("takes everything for null", () => {
    expect(latest(five, null)).toHaveLength(5);
  });

  it("is never short of what is stored", () => {
    expect(latest(five, 10)).toHaveLength(5);
  });
});

describe("the counted figures", () => {
  it("counts distinct scenarios and partners, and the span of the whole set", () => {
    const counts = activity([
      session({ started_at: "2026-09-03T10:00:00Z", scenario: "A", persona: "X" }),
      session({ started_at: "2026-09-01T10:00:00Z", scenario: "A", persona: "Y" }),
      session({ started_at: "2026-09-02T10:00:00Z", scenario: "B", persona: "X" }),
    ]);

    expect(counts).toMatchObject({ sessions: 3, scenarios: 2, personas: 2 });
    expect(counts.firstAt).toBe("2026-09-01T10:00:00Z");
    expect(counts.lastAt).toBe("2026-09-03T10:00:00Z");
  });

  it("has no span with nothing stored", () => {
    expect(activity([])).toMatchObject({ sessions: 0, firstAt: null, lastAt: null });
  });

  it("counts finished trainings only, like the calendar beside it", () => {
    // ADR 0034: an aborted call is kept, not counted.
    const counts = activity([
      session({ started_at: "2026-09-03T10:00:00Z", scenario: "A", persona: "X" }),
      session({ started_at: "2026-09-02T10:00:00Z", scenario: "B", persona: "Y", status: "aborted" }),
      session({ started_at: "2026-09-01T10:00:00Z", scenario: "A", persona: "X" }),
    ]);

    expect(counts).toMatchObject({ sessions: 2, scenarios: 1, personas: 1 });
    expect(counts.firstAt).toBe("2026-09-01T10:00:00Z");
    expect(counts.lastAt).toBe("2026-09-03T10:00:00Z");
  });
});

describe("the calls long enough to read figures from", () => {
  const long = (over = {}) =>
    session({ started_at: "2026-09-01T10:00:00Z", ended_at: "2026-09-01T10:05:00Z", ...over });
  const short = (over = {}) =>
    session({ started_at: "2026-09-01T10:00:00Z", ended_at: "2026-09-01T10:00:20Z", ...over });

  it("drops a call too short to describe", () => {
    expect(readable([long(), short(), long()])).toHaveLength(2);
  });

  it("keeps a long call that ended badly, and drops a short one that ended well", () => {
    // On length, not status: `aborted` also means a dropped connection.
    const kept = readable([long({ status: "aborted" }), short({ status: "completed" })]);

    expect(kept).toHaveLength(1);
    expect(kept[0]?.status).toBe("aborted");
  });

  it("keeps a call whose length cannot be worked out", () => {
    // Dropping a possibly full call is the worse mistake.
    expect(readable([session({ ended_at: null })])).toHaveLength(1);
  });

  it("is what the series are built from, so no caller can forget it", () => {
    const series = selectionSeries([
      long({ measurements: [measurement("pace", 120)] }),
      short({ measurements: [measurement("pace", 300)] }),
    ]);

    expect(series.find((s) => s.key === "pace")?.points.map((p) => p.value)).toEqual([120]);
  });

  it("counts the finished and the readable separately, because they answer different questions", () => {
    const sessions = [long(), short(), long({ status: "aborted" })];

    expect(completedOnly(sessions)).toHaveLength(2);
    expect(readable(sessions)).toHaveLength(2);
  });
});

describe("how long a call ran", () => {
  it("is the two timestamps apart", () => {
    expect(
      callDurationMs(
        session({ started_at: "2026-09-01T10:00:00Z", ended_at: "2026-09-01T10:06:00Z" }),
      ),
    ).toBe(6 * 60 * 1000);
  });

  it("is absent where the Session has no recorded end", () => {
    expect(callDurationMs(session({ ended_at: null }))).toBeNull();
  });

  it("is absent rather than negative where the end precedes the start", () => {
    expect(
      callDurationMs(
        session({ started_at: "2026-09-01T10:06:00Z", ended_at: "2026-09-01T10:00:00Z" }),
      ),
    ).toBeNull();
  });

  it("reads as minutes, oldest first, and skips the calls without an end", () => {
    const series = durationSeries([
      session({ started_at: "2026-09-02T10:00:00Z", ended_at: "2026-09-02T10:03:00Z" }),
      session({ started_at: "2026-09-01T12:00:00Z", ended_at: null }),
      session({ started_at: "2026-09-01T10:00:00Z", ended_at: "2026-09-01T10:06:00Z" }),
    ]);

    expect(series?.points.map((p) => p.value)).toEqual([6, 3]);
  });

  it("is absent where no call has an end at all", () => {
    expect(durationSeries([session({ ended_at: null })])).toBeNull();
  });
});

describe("the series of a selection", () => {
  // Every progress screen reads this one list.
  it("carries the call length beside the measured metrics", () => {
    const keys = selectionSeries([
      session({ measurements: [measurement("pace", 130)] }),
    ]).map((s) => s.key);
    expect(keys).toEqual(["pace", "duration"]);
  });
});

describe("the calendar month", () => {
  /** Midday, so no timezone shifts the day. */
  const onDay = (day: number, over: Partial<Parameters<typeof session>[0]> = {}) =>
    session({ started_at: new Date(2026, 8, day, 12, 0, 0).toISOString(), ...over });

  it("pads to whole weeks with Monday first", () => {
    const month = activityMonth([], 2026, 8);
    expect(month.weeks[0]?.[0]).toBeNull();
    expect(month.weeks[0]?.[1]?.dayOfMonth).toBe(1);
    for (const week of month.weeks) expect(week).toHaveLength(7);
  });

  it("counts completed trainings per day and in the month's own total", () => {
    const month = activityMonth([onDay(3), onDay(3), onDay(10)], 2026, 8);
    const days = month.weeks.flat().filter((d) => d !== null);

    expect(days.find((d) => d.dayOfMonth === 3)?.count).toBe(2);
    expect(days.find((d) => d.dayOfMonth === 10)?.count).toBe(1);
    expect(days.find((d) => d.dayOfMonth === 4)?.count).toBe(0);
    expect(month.total).toBe(3);
  });

  it("neither counts nor marks an abandoned call", () => {
    const month = activityMonth([onDay(3, { status: "aborted" })], 2026, 8);
    expect(month.total).toBe(0);
  });

  it("leaves a training in another month out", () => {
    expect(activityMonth([onDay(3)], 2026, 7).total).toBe(0);
  });

  it("shades in three steps, because a day holds one, two or a handful", () => {
    expect([0, 1, 2, 3, 9].map(activityStep)).toEqual([0, 1, 2, 3, 3]);
  });

  it("keys a late-evening training on the day it happened", () => {
    // Local parts: `toISOString` pushes 23:30 into the next day east of UTC.
    const late = new Date(2026, 8, 3, 23, 30, 0);
    expect(dayKey(late)).toBe("2026-8-3");
  });

  it("pages back to the month of the oldest completed training", () => {
    expect(
      firstTrainingMonth([onDay(20), session({ started_at: new Date(2026, 5, 4).toISOString() })]),
    ).toEqual({ year: 2026, month: 5 });
  });

  it("does not page back to an abandoned call", () => {
    expect(
      firstTrainingMonth([
        onDay(20),
        session({ started_at: new Date(2026, 5, 4).toISOString(), status: "aborted" }),
      ]),
    ).toEqual({ year: 2026, month: 8 });
  });

  it("has nowhere to page with nothing stored", () => {
    expect(firstTrainingMonth([])).toBeNull();
  });

  it("lists exactly the trainings a cell counted", () => {
    // Same `dayKey`, so a cell saying 2 never lists three.
    const sessions = [onDay(3), onDay(3), onDay(4)];
    const counted = activityMonth(sessions, 2026, 8)
      .weeks.flat()
      .find((d) => d?.dayOfMonth === 3)?.count;

    expect(counted).toBe(2);
    expect(trainingsOn(sessions, new Date(2026, 8, 3))).toHaveLength(2);
  });

  it("lists no abandoned call, which the cell did not count either", () => {
    expect(trainingsOn([onDay(3, { status: "aborted" })], new Date(2026, 8, 3))).toEqual([]);
  });

  it("lists nothing for a day nothing happened on", () => {
    expect(trainingsOn([onDay(3)], new Date(2026, 8, 4))).toEqual([]);
  });
});

describe("the trainings behind a variety cell", () => {
  it("are the ones on that pairing and no other", () => {
    const wanted = session({ scenario: "A", persona: "X" });
    const sessions = [
      wanted,
      session({ scenario: "A", persona: "Y" }),
      session({ scenario: "B", persona: "X" }),
    ];

    expect(trainingsWith(sessions, "A", "X")).toEqual([wanted]);
  });

  it("leave out an abandoned call, exactly as the cell does", () => {
    const sessions = [
      session({ scenario: "A", persona: "X" }),
      session({ scenario: "A", persona: "X", status: "aborted" }),
    ];

    expect(variety(sessions).cells[0]?.count).toBe(1);
    expect(trainingsWith(sessions, "A", "X")).toHaveLength(1);
  });
});

describe("what was played against whom", () => {
  it("holds only the combinations that occurred", () => {
    // Played combinations only.
    const grid = variety([
      session({ scenario: "A", persona: "X" }),
      session({ scenario: "A", persona: "X" }),
      session({ scenario: "B", persona: "Y" }),
    ]);

    expect(grid.cells).toHaveLength(2);
    expect(grid.cells.find((c) => c.scenario === "A")?.count).toBe(2);
  });

  it("orders both sides most played first", () => {
    const grid = variety([
      session({ scenario: "selten", persona: "X" }),
      session({ scenario: "oft", persona: "X" }),
      session({ scenario: "oft", persona: "X" }),
    ]);

    expect(grid.scenarios).toEqual(["oft", "selten"]);
  });

  it("breaks a tie alphabetically, so two reads of the same data agree", () => {
    const grid = variety([
      session({ scenario: "Zweites", persona: "X" }),
      session({ scenario: "Erstes", persona: "X" }),
    ]);

    expect(grid.scenarios).toEqual(["Erstes", "Zweites"]);
  });
});

describe("what stands in for the focus goals", () => {
  const history = (values: Record<string, number[]>) =>
    [0, 1, 2, 3].map((i) =>
      session({
        started_at: `2026-09-0${4 - i}T10:00:00Z`,
        measurements: Object.entries(values)
          .filter(([, v]) => v[i] !== undefined)
          .map(([key, v]) => measurement(key, v[i] as number)),
      }),
    );

  it("orders by spread relative to the middle, so units can be compared", () => {
    // Relative to the middle, which the reaction time below needs.
    const series = toSeries(
      history({ pace: [100, 140, 120, 125], talk_share: [49, 51, 50, 50], reaction_time: [0.5, 1.5, 1, 1] }),
    );

    expect(mostVarying(series, 3).map((s) => s.key)).toEqual(["reaction_time", "pace", "talk_share"]);
  });

  it("leaves out a series too short to have a spread", () => {
    const series = toSeries(history({ pace: [100, 140, 120, 125], fillers: [1, 9] }));

    expect(mostVarying(series, 3).map((s) => s.key)).toEqual(["pace"]);
  });

  it("stops at the count it is asked for", () => {
    const series = toSeries(
      history({ pace: [100, 140, 120, 125], talk_share: [40, 60, 50, 50], reaction_time: [0.5, 1.5, 1, 1] }),
    );

    expect(mostVarying(series, 2)).toHaveLength(2);
  });
});
