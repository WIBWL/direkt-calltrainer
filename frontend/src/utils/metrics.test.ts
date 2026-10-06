import { describe, expect, it } from "vitest";

import type { Measurement } from "../protocol";
import {
  comparableAcrossCalls,
  formatNumber,
  formatValue,
  isCount,
  metricParts,
  metricSubline,
  partsTotal,
  seriesShape,
  showsInOverview,
  withDerived,
} from "./metrics";

/** ADR 0082: a metric's display facts, the one table every screen reads. */

const measurement = (over: Partial<Measurement> & Pick<Measurement, "key">): Measurement => ({
  name: over.key,
  unit: null,
  aspect: "how",
  value: 0,
  detail: null,
  ...over,
});

describe("writing a figure out", () => {
  it("uses the German decimal comma", () => {
    expect(formatValue("reaction_time", 1.8, "s")).toBe("1,8 s");
    expect(formatNumber(16.25, 1)).toBe("16,3");
  });

  it("gives a rate no decimals, because nobody speaks 132,4 words a minute", () => {
    expect(formatValue("pace", 132.4, "W/min")).toBe("132 W/min");
    expect(formatValue("talk_share", 46.2, "%")).toBe("46 %");
  });

  it("gives an unnamed metric one decimal", () => {
    // An unknown key renders plainly.
    expect(formatValue("redeanteil", 46.25, "%")).toBe("46,3 %");
  });

  it("prints a count without the word 'Anzahl'", () => {
    expect(isCount("Anzahl")).toBe(true);
    expect(formatValue("questions", 4, "Anzahl")).toBe("4");
  });

  it("rounds a count to a whole number", () => {
    expect(formatValue("interruptions", 2.0, "Anzahl")).toBe("2");
  });
});

describe("which metrics reach which screen", () => {
  it("keeps the loudness off every cross-call view", () => {
    // ADR 0076; an explicit field, so a new metric is never silently comparable.
    expect(comparableAcrossCalls("loudness")).toBe(false);
    expect(comparableAcrossCalls("pace")).toBe(true);
  });

  it("keeps the word count out of the overview but not out of the application", () => {
    expect(showsInOverview("word_count")).toBe(false);
    expect(comparableAcrossCalls("word_count")).toBe(true);
  });

  it("lets an unknown key through rather than dropping it", () => {
    expect(comparableAcrossCalls("redeanteil")).toBe(true);
    expect(showsInOverview("redeanteil")).toBe(true);
  });
});

describe("the checklist metrics", () => {
  it("draws them as marks and not as a line", () => {
    expect(seriesShape("opening")).toBe("parts");
    expect(seriesShape("closing")).toBe("parts");
    expect(seriesShape("pace")).toBe("line");
  });

  it("credits the opening with three parts although it lists four", () => {
    // The offer of help or the concern, by who rang.
    expect(partsTotal("opening")).toBe(3);
    expect(partsTotal("closing")).toBe(3);
    expect(partsTotal("pace")).toBeNull();
  });

  it("shows only the parts the call was actually checked for", () => {
    // Showing both would mark one unrecognised in every call.
    const parts = metricParts(
      measurement({
        key: "opening",
        detail: { greeting: true, name: false, offer: true },
      }),
    );

    expect(parts).toEqual([
      { key: "greeting", label: "Begrüßung", said: true },
      { key: "name", label: "Name", said: false },
      { key: "offer", label: "Hilfsangebot", said: true },
    ]);
  });

  it("names the concern instead where that is what was checked", () => {
    const parts = metricParts(
      measurement({ key: "opening", detail: { greeting: true, name: true, concern: false } }),
    );

    expect(parts?.map((p) => p.key)).toEqual(["greeting", "name", "concern"]);
  });

  it("has no parts for an ordinary metric", () => {
    expect(metricParts(measurement({ key: "pace", value: 130 }))).toBeNull();
  });
});

describe("the second line under a figure", () => {
  it("splits the questions into open and closed", () => {
    expect(
      metricSubline(measurement({ key: "questions", value: 4, detail: { open: 3, closed: 1 } })),
    ).toBe("davon 3 offen, 1 geschlossen");
  });

  it("says where the closing was looked for, with the backend's own number", () => {
    expect(metricSubline(measurement({ key: "closing", detail: { turns_read: 2 } }))).toBe(
      "geprüft: Ihre letzten 2 Beiträge",
    );
    expect(metricSubline(measurement({ key: "closing", detail: { turns_read: 1 } }))).toBe(
      "geprüft: Ihr letzter Beitrag",
    );
  });

  it("calls the hesitation count an estimate on the tile itself", () => {
    expect(metricSubline(measurement({ key: "hesitations", value: 5 }))).toBe(
      "geschätzt aus der Tonhöhe",
    );
  });

  it("says nothing where the detail is missing", () => {
    expect(metricSubline(measurement({ key: "questions", value: 4 }))).toBeNull();
    expect(metricSubline(measurement({ key: "pace", value: 130 }))).toBeNull();
  });
});

describe("the figure derived from another", () => {
  it("lifts the sentence length out of the word count's detail", () => {
    const derived = withDerived([
      measurement({ key: "word_count", value: 420, detail: { words_per_sentence: 12.4 } }),
    ]);

    expect(derived.map((m) => m.key)).toEqual(["word_count", "words_per_sentence"]);
    expect(derived[1]?.value).toBe(12.4);
  });

  it("adds nothing where the call has no such figure", () => {
    const measurements = [measurement({ key: "word_count", value: 420 })];
    expect(withDerived(measurements)).toEqual(measurements);
  });
});
