import { describe, expect, it } from "vitest";

import { measurement, session } from "../test/sessions";
import {
  activity,
  activityMonth,
  activityStep,
  band,
  callDurationMs,
  completeParts,
  dayKey,
  durationSeries,
  firstTrainingMonth,
  formatBand,
  formatPoint,
  halves,
  latest,
  median,
  mostVarying,
  selectionSeries,
  toSeries,
  trainingsOn,
  trainingsWith,
  variety,
} from "./progressStats";

/** The arithmetic behind the progress dashboard (F-13): every failure here renders
 * perfectly, so the cases pin the claims the screen makes out loud ("Ihr üblicher
 * Bereich 118 bis 141", "in 9 von 12 Trainings"). Nothing may grow a target or a
 * direction (ADR 0051/0065); `band` is where one would arrive first. */

// --- Series -----------------------------------------------------------------

describe("building a series from the history", () => {
  it("turns the newest-first history into points oldest first", () => {
    // The history arrives newest first (ADR 0064) and a chart reads left to
    // right in time. Reversed, every course on the dashboard tells its story
    // backwards while looking entirely healthy.
    const series = toSeries([
      session({ started_at: "2026-09-03T10:00:00Z", measurements: [measurement("pace", 3)] }),
      session({ started_at: "2026-09-02T10:00:00Z", measurements: [measurement("pace", 2)] }),
      session({ started_at: "2026-09-01T10:00:00Z", measurements: [measurement("pace", 1)] }),
    ]);

    expect(series).toHaveLength(1);
    expect(series[0]?.points.map((p) => p.value)).toEqual([1, 2, 3]);
  });

  it("leaves out a measurement whose metric type has been retired", () => {
    // A Session measured before ADR 0057's rename points at the old row, which
    // carries the same display name as its replacement. Kept, the dashboard
    // would draw two charts called "Redeanteil" side by side.
    const series = toSeries([
      session({
        measurements: [
          measurement("talk_share", 40),
          measurement("redeanteil", 40, { active: false }),
        ],
      }),
    ]);

    expect(series.map((s) => s.key)).toEqual(["talk_share"]);
  });

  it("leaves out the loudness, which is not comparable between calls", () => {
    // Its dB span is the recording level, so across calls it measures the
    // microphone and the distance as much as the speaker (ADR 0076's
    // amendment). The single call's own page keeps it.
    const series = toSeries([
      session({ measurements: [measurement("loudness", 12), measurement("pace", 130)] }),
    ]);

    expect(series.map((s) => s.key)).toEqual(["pace"]);
  });

  it("gives a checklist metric no band, whatever its values", () => {
    // A course of 1-3-2-3 over a band reads as a score climbing to full marks,
    // which is the reading ADR 0086 kept off the single call's tile.
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

// --- The usual range --------------------------------------------------------

describe("the user's own usual range", () => {
  it("describes nothing below three values", () => {
    expect(band([10, 20])).toBeNull();
  });

  it("is the median widened by the median absolute deviation", () => {
    // 1, 2, 3, 4, 100: median 3, deviations 2, 1, 0, 1, 97, median of those 1.
    // The outlier moves the band by nothing, which is the whole reason for a
    // MAD over a standard deviation.
    expect(band([1, 2, 3, 4, 100])).toEqual({ median: 3, low: 2, high: 4 });
  });

  it("falls back to the mean deviation where more than half the values are equal", () => {
    // 5, 5, 5, 9: the MAD is 0 because three of four sit on the median, and a
    // band of zero width would claim somebody always speaks at exactly 5.
    const result = band([5, 5, 5, 9]);
    expect(result?.median).toBe(5);
    expect(result?.high).toBeCloseTo(6, 10);
    expect(result?.low).toBeCloseTo(4, 10);
  });

  it("has no width at all where every value is identical", () => {
    // Neither deviation separates a constant series, and inventing a width for
    // it would be the first threshold on this screen.
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
    // 0, 0, 0, 5, 5: the median is 0 and the spread 2, so the band runs from
    // -2 on paper. "-2 bis 2 Unterbrechungen" describes nothing anybody did.
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

    // The dot was simply wrong in German, and the low end carries no unit.
    expect(formatBand(series)).toBe("1,2 bis 2,4 s");
  });
});

describe("the earlier half and the recent one", () => {
  /** A pace series whose values arrive oldest first in the chart. The history
   *  is newest first, so the fixture is written the other way round. */
  const paces = (values: number[]) =>
    toSeries(
      [...values]
        .reverse()
        .map((value) => session({ measurements: [measurement("pace", value)] })),
    )[0]!;

  it("describes each half on its own terms", () => {
    // 10, 10, 10 and 20, 20, 20: two medians, two spreads, and nothing
    // computed between them.
    const split = halves(paces([10, 10, 10, 20, 20, 20]));

    expect(split).toEqual({
      each: 3,
      early: { median: 10, low: 10, high: 10 },
      late: { median: 20, low: 20, high: 20 },
    });
  });

  it("computes no difference, no ratio and no direction", () => {
    // The assertion that notices a delta being added. ADR 0065 rules one out by
    // name, and this is the function where it would arrive.
    const split = halves(paces([10, 10, 10, 20, 20, 20]));

    expect(Object.keys(split ?? {}).sort()).toEqual(["each", "early", "late"]);
  });

  it("leaves the middle training out of an odd count", () => {
    // In both halves it would pull them towards each other; in one it would
    // make the two rest on different numbers of calls.
    const split = halves(paces([1, 2, 3, 99, 7, 8, 9]));

    expect(split?.each).toBe(3);
    expect(split?.early.median).toBe(2);
    expect(split?.late.median).toBe(8);
  });

  it("says nothing below twice the series threshold", () => {
    // A usual range over two values describes nothing, and two of those beside
    // each other describe nothing twice.
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
    // "2 von 3" is what reads as a mark, and "erkannt" keeps it a detection,
    // which is all it is — a bare name slips past the patterns (F-63).
    expect(formatPoint(openings([2]), 2)).toBe("2 Teile erkannt");
    expect(formatPoint(openings([1]), 1)).toBe("1 Teil erkannt");
  });

  it("counts the trainings in which every part was there", () => {
    // Newest first in, so this is 3, 3, 2 — two complete.
    expect(completeParts(openings([2, 3, 3]))).toBe(2);
  });

  it("has nothing to count for an ordinary metric", () => {
    const pace = toSeries([session({ measurements: [measurement("pace", 130)] })])[0]!;
    expect(completeParts(pace)).toBeNull();
  });
});

// --- The selection ----------------------------------------------------------

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
});

// --- Call length ------------------------------------------------------------

describe("how long a call ran", () => {
  it("is the two timestamps apart", () => {
    expect(
      callDurationMs(
        session({ started_at: "2026-09-01T10:00:00Z", ended_at: "2026-09-01T10:06:00Z" }),
      ),
    ).toBe(6 * 60 * 1000);
  });

  it("is absent where the Session has no recorded end", () => {
    // A call cut short by a pipeline failure legitimately may not have one.
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
  // The overview, a metric's page and a goal's page all read this one list, so
  // a row the overview links to is one the page behind the link can find. The
  // call length was the row that went missing: only the overview added it.
  it("carries the call length beside the measured metrics", () => {
    const keys = selectionSeries([
      session({ measurements: [measurement("pace", 130)] }),
    ]).map((s) => s.key);
    expect(keys).toEqual(["pace", "duration"]);
  });
});

// --- The calendar -----------------------------------------------------------

describe("the calendar month", () => {
  /** A training at midday local time on the given day of September 2026, so the
   *  fixture cannot slide into a neighbouring day in any timezone the suite
   *  runs in. */
  const onDay = (day: number, over: Partial<Parameters<typeof session>[0]> = {}) =>
    session({ started_at: new Date(2026, 8, day, 12, 0, 0).toISOString(), ...over });

  it("pads to whole weeks with Monday first", () => {
    // 1 September 2026 is a Tuesday, so one empty cell leads.
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
    // The calendar answers "when did I train", and a call that broke off is
    // not an answer to it (ADR 0034's amendment).
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
    // Built from the local parts rather than from `toISOString`, which would
    // push a 23:30 call into the next day for anybody east of UTC — and the
    // "today" ring is read with the same key, so the two cannot disagree.
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
    // The list under the calendar and the number in the cell are read off the
    // same `dayKey`, so they cannot disagree — a cell saying 2 over a list of
    // three is the defect this pins.
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

  it("include an abandoned call, because the cell counted it", () => {
    // `variety` has no status filter, so the list must not have one either, or
    // a cell saying 2 would open onto one row.
    const sessions = [
      session({ scenario: "A", persona: "X" }),
      session({ scenario: "A", persona: "X", status: "aborted" }),
    ];

    expect(variety(sessions).cells[0]?.count).toBe(2);
    expect(trainingsWith(sessions, "A", "X")).toHaveLength(2);
  });
});

// --- The variety grid -------------------------------------------------------

describe("what was played against whom", () => {
  it("holds only the combinations that occurred", () => {
    // A grid of everything the library offers with the unplayed cells empty
    // would turn a description of what somebody did into a list of what they
    // have not.
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
    // Pace moves by 40 around 120, a third; talk share by 2 around 50, a
    // twenty-fifth. In absolute terms pace would win anyway — the reaction
    // time below is what the relative measure is for.
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
