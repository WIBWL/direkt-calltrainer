/** Finds what a metric counted, for quoting (ADR 0098); never recomputes. Mirrors
 * the backend's `metrics._questions` and `metrics._fillers`: change those, change this. */

const SENTENCE_END = /[.!?]/;

const MAX_HITS = 5;

/** One per question mark, each from the end of the previous sentence. */
export function questionsIn(text: string): string[] {
  const found: string[] = [];
  let start = 0;

  for (let i = 0; i < text.length; i += 1) {
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

function sentencesOf(text: string): string[] {
  const parts = text.split(/(?<=[.!?])\s+/);
  return parts.map((part) => part.trim()).filter((part) => part.length > 0);
}

export interface FillerHit {
  before: string;
  /** As said; this is what gets marked. */
  word: string;
  after: string;
  at: number;
}

/** One per sentence, most frequent words first: the habit, not the accident. */
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

/** Case-insensitive and whole-word, as the backend matches. */
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

/** Letters only, so a hyphen or comma is a boundary. */
function isWholeWord(text: string, index: number, length: number): boolean {
  const before = index === 0 ? "" : text[index - 1] ?? "";
  const after = text[index + length] ?? "";
  return !isLetter(before) && !isLetter(after);
}

function isLetter(char: string): boolean {
  return char.length > 0 && char.toLowerCase() !== char.toUpperCase();
}
