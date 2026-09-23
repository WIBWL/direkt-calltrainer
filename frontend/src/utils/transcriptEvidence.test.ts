import { describe, expect, it } from "vitest";

import { fillerHits, questionsIn } from "./transcriptEvidence";

/**
 * What a metric's page quotes as the evidence behind its figure (ADR 0098).
 *
 * These reproduce the backend's own counting rule, and the module says so: a
 * count and a list of quotations that disagree is worse than either alone. The
 * failure mode is silent — the page shows four quotes under a figure of five
 * and looks perfectly healthy — so the arithmetic is pinned here.
 */

describe("questionsIn", () => {
  it("quotes the question alone, not the sentence before it", () => {
    expect(questionsIn("Guten Tag. Wie kann ich helfen?")).toEqual([
      "Wie kann ich helfen?",
    ]);
  });

  it("returns one entry per question mark, which is what the metric counts", () => {
    const text = "Wie geht es? Und Ihnen? Alles gut.";
    expect(questionsIn(text)).toEqual(["Wie geht es?", "Und Ihnen?"]);
  });

  it("keeps a question mark inside a sentence, which a sentence split would drop", () => {
    // The backend counts the character, so this has to count it too.
    const text = "Sie fragen: wann kommt der Techniker? und ich verstehe das.";
    expect(questionsIn(text)).toHaveLength(1);
    expect(questionsIn(text)[0]).toBe(
      "Sie fragen: wann kommt der Techniker?",
    );
  });

  it("finds nothing in a turn that asked nothing", () => {
    expect(questionsIn("Ich schicke Ihnen das Angebot bis Freitag.")).toEqual([]);
    expect(questionsIn("")).toEqual([]);
  });

  it("still quotes a stray question mark, because the metric counted it", () => {
    // Ugly on the page and deliberate all the same: the backend counts the
    // character, so dropping this would put four quotes under a figure of
    // five. The module's contract is that the two agree, and a prettier quote
    // list is not worth breaking it for.
    expect(questionsIn("Ja. ?")).toEqual(["?"]);
  });
});

describe("fillerHits", () => {
  const turn = (text: string, at = 0) => ({ text, at });

  it("splits the sentence around the counted word", () => {
    const hits = fillerHits([turn("Das ist eigentlich kein Problem.")], ["eigentlich"]);

    expect(hits).toHaveLength(1);
    expect(hits[0]).toEqual({
      before: "Das ist ",
      word: "eigentlich",
      after: " kein Problem.",
      at: 0,
    });
  });

  it("quotes the word as it was said, not as it was counted", () => {
    // The detail lists the word lower-cased; the sentence keeps its capital.
    const hits = fillerHits([turn("Eigentlich schon.")], ["eigentlich"]);

    expect(hits[0]?.word).toBe("Eigentlich");
  });

  it("matches a whole word only, never inside a longer one", () => {
    expect(fillerHits([turn("Die Eigentlichkeit der Sache.")], ["eigentlich"])).toEqual([]);
  });

  it("treats punctuation and hyphens as word boundaries", () => {
    const hits = fillerHits([turn("Also, das passt.")], ["also"]);

    expect(hits).toHaveLength(1);
    expect(hits[0]?.after).toBe(", das passt.");
  });

  it("quotes a sentence once even when it carries two fillers", () => {
    const hits = fillerHits(
      [turn("Also das ist eigentlich so.")],
      ["also", "eigentlich"],
    );

    expect(hits).toHaveLength(1);
    // The earliest of the words in the sentence, whichever order they arrived in.
    expect(hits[0]?.word).toBe("Also");
  });

  it("carries the offset of the turn the sentence sat in", () => {
    const hits = fillerHits(
      [turn("Ja genau.", 1000), turn("Also gut.", 45000)],
      ["also"],
    );

    expect(hits[0]?.at).toBe(45000);
  });

  it("stops at five hits, so a long call stays readable", () => {
    const turns = Array.from({ length: 9 }, (_, i) => turn(`Also Satz ${i}.`, i * 1000));

    expect(fillerHits(turns, ["also"])).toHaveLength(5);
  });

  it("returns nothing when the metric counted no words", () => {
    expect(fillerHits([turn("Also gut.")], [])).toEqual([]);
  });
});
