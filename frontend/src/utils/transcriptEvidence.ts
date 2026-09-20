/**
 * Finding in the stored transcript what a metric counted (ADR 0098).
 *
 * The figures themselves are measured once, when the call ends, and are never
 * recomputed here (ADR 0051). What these functions do is locate the passage a
 * figure came from, so the metric's page can quote it. A count and a list of
 * quotations that disagree would be worse than either alone, so each function
 * below is written to reproduce the backend's own rule rather than a reasonable
 * approximation of it:
 *
 * - questions are cut at the question marks, because `metrics._questions`
 *   counts exactly those characters,
 * - a filler is matched as a whole phrase, lower-cased and with runs of
 *   whitespace closed, which is the form `metrics._fillers` counts in.
 *
 * Where a rule changes on the backend, this file is the second place to look.
 * It is in the frontend all the same: the sentences are in the transcript the
 * detail route already serves, and an endpoint that returned the same words a
 * second time would be a second copy to keep in step.
 */

/** Ends a sentence, in the punctuation the speech recogniser writes. */
const SENTENCE_END = /[.!?]/;

/** How many quoted hits a page shows before it stops. Enough to recognise a
 *  habit, few enough that the page stays readable under a long call. */
const MAX_HITS = 5;

/**
 * The questions in one turn, one entry per question mark.
 *
 * Each runs from the end of the previous sentence up to its own question mark,
 * so a turn that says "Guten Tag. Wie kann ich helfen?" quotes only the
 * question. The count therefore matches the metric exactly, which a split on
 * sentence boundaries would not: a question mark inside a sentence would be
 * counted by the backend and dropped here.
 */
export function questionsIn(text: string): string[] {
  const found: string[] = [];
  let start = 0;

  for (let i = 0; i < text.length; i += 1) {
    // `?? ""` because the compiler checks every index access here, and an
    // out-of-range read is impossible inside this loop.
    const char = text[i] ?? "";
    if (char === "?") {
      found.push(text.slice(start, i + 1).trim());
      start = i + 1;
    } else if (SENTENCE_END.test(char)) {
      start = i + 1;
    }
  }

  return found.filter((question) => question.length > 0);
}

/** The sentences of one stretch of transcript, punctuation kept. */
export function sentencesOf(text: string): string[] {
  const parts = text.split(/(?<=[.!?])\s+/);
  return parts.map((part) => part.trim()).filter((part) => part.length > 0);
}

export interface FillerHit {
  /** The sentence up to the word. */
  before: string;
  /** The word as it was said, which is what gets marked. */
  word: string;
  /** The rest of the sentence. */
  after: string;
  /** When the turn it sits in began. */
  at: number;
}

/**
 * Where the counted filler words fall in the call, at most `MAX_HITS` of them.
 *
 * One hit per sentence at most: a sentence with two fillers in it would
 * otherwise be quoted twice, and the second copy tells a reader nothing the
 * first did not. The words arrive in the order the detail lists them, which is
 * most frequent first, so a shortened list shows the habit rather than the
 * accident.
 */
export function fillerHits(
  turns: { text: string; at: number }[],
  words: string[],
): FillerHit[] {
  if (words.length === 0) return [];

  const hits: FillerHit[] = [];

  for (const turn of turns) {
    for (const sentence of sentencesOf(turn.text)) {
      const found = firstWord(sentence, words);
      if (!found) continue;
      hits.push({
        before: sentence.slice(0, found.index),
        word: sentence.slice(found.index, found.index + found.length),
        after: sentence.slice(found.index + found.length),
        at: turn.at,
      });
      if (hits.length >= MAX_HITS) return hits;
    }
  }

  return hits;
}

/** The earliest of these words in one sentence, matched the way the backend
 *  matched it: case-insensitive, and as a whole word rather than inside a
 *  longer one ("eigentlich" must not match inside a compound). */
function firstWord(
  sentence: string,
  words: string[],
): { index: number; length: number } | null {
  const haystack = sentence.toLowerCase();
  let best: { index: number; length: number } | null = null;

  for (const word of words) {
    const needle = word.toLowerCase();
    let from = 0;
    for (;;) {
      const index = haystack.indexOf(needle, from);
      if (index < 0) break;
      if (isWholeWord(haystack, index, needle.length)) {
        if (!best || index < best.index) best = { index, length: needle.length };
        break;
      }
      from = index + 1;
    }
  }

  return best;
}

/** Whether a match sits on its own rather than inside a longer word. Letters
 *  only, so a hyphen or a comma counts as a boundary. */
function isWholeWord(text: string, index: number, length: number): boolean {
  const before = index === 0 ? "" : text[index - 1] ?? "";
  const after = text[index + length] ?? "";
  return !isLetter(before) && !isLetter(after);
}

function isLetter(char: string): boolean {
  return char.length > 0 && char.toLowerCase() !== char.toUpperCase();
}
