import { useEffect, useState, type CSSProperties } from "react";

import type { FeedbackState } from "../hooks/useSessionFeedback";

/** The bars of the waveform being read, as a share of the scene's height.
 * Uneven on purpose: an even row is a loading indicator, an uneven one is a
 * recording of somebody talking. */
const BARS = [26, 52, 74, 44, 96, 62, 34, 70, 40, 58, 28];

/** How long one line stands before the next takes over. Long enough to read
 * twice, short enough that the screen never looks stuck. */
const CAPTION_MS = 3400;

/**
 * What the wait is actually spent on, in the order it roughly happens. Light,
 * because this screen is the pause after a conversation the User has just had
 * to concentrate through — but every line is true of what the worker is doing,
 * which is what keeps it from reading as filler.
 */
const CAPTIONS = [
  "Das Gespräch wird abgetippt …",
  "Ihre Sprechpausen werden vermessen …",
  "Ähms werden wohlwollend überhört …",
  "Ihre Fragen werden gezählt …",
  "Es wird nach Ihren besten Momenten gesucht …",
  "Die Zusammenfassung wird geschrieben …",
];

/**
 * How long this screen waits before handing over regardless.
 *
 * `useSessionFeedback` polls for ten minutes (the worker's own timeout), which
 * is the right patience for a block on a page and the wrong one for a screen
 * that holds nothing else: a wrap-up that takes that long is one the User
 * should be reading their transcript instead of waiting for. The poll is not
 * lost by moving on — it carries on behind the post-call screen, and the
 * wrap-up appears there when it lands.
 */
const WAIT_LIMIT_MS = 120_000;

/**
 * The screen between hanging up and the wrap-up (F-09/F-10): the report is
 * written in the worker (ADR 0049), so there is a real wait here, and it used
 * to be spent looking at a finished-looking page with one grey line on it
 * saying the interesting part was still coming.
 *
 * So the wait gets a screen of its own and something to watch. The animation
 * is the whole content — under `prefers-reduced-motion` the scene stands still
 * (see index.css) rather than being dropped, because unlike the die (F-62) or
 * the card turn (F-61) there is nothing behind it to skip to.
 *
 * It is never shown for a Session that was not stored: without consent there
 * is no wrap-up on the way (ADR 0066), and a wait for something that is not
 * coming is the one thing this screen must not be. The caller decides that —
 * see App.tsx, which only enters this screen with a `sessionId` in hand.
 */
export default function FeedbackWaiting({
  state,
  onDone,
}: {
  /** Where the wrap-up's poll stands. `App` runs it once for this screen and
   * the post-call screen together. */
  state: FeedbackState;
  /** Move on to the post-call screen — because the wrap-up has settled, one
   * way or the other, or because the User would rather read the transcript. */
  onDone: () => void;
}) {
  const [caption, setCaption] = useState(0);

  // "loading" is the only state that is still waiting for something: a wrap-up
  // that failed or was never stored has settled too, and the post-call screen
  // says which of the two it was.
  useEffect(() => {
    if (state !== "loading") onDone();
  }, [state, onDone]);

  useEffect(() => {
    const id = window.setInterval(
      () => setCaption((i) => (i + 1) % CAPTIONS.length),
      CAPTION_MS,
    );
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const id = window.setTimeout(onDone, WAIT_LIMIT_MS);
    return () => window.clearTimeout(id);
  }, [onDone]);

  return (
    <div className="feedback-wait">
      <div className="eyebrow">TRAINING ABGESCHLOSSEN</div>
      <h1 className="feedback-title">Ihr Feedback wird erstellt</h1>

      <div className="feedback-wait-stage" aria-hidden="true">
        <div className="feedback-wait-wave">
          {BARS.map((height, i) => (
            <span
              key={i}
              className="feedback-wait-bar"
              style={{ "--h": `${height}%`, "--i": i } as CSSProperties}
            />
          ))}
        </div>

        {/* Passes over the waveform and back, which is what turns a row of
            bouncing bars into something being *read*. */}
        <div className="feedback-wait-lens">
          <svg viewBox="0 0 52 52" width="52" height="52" focusable="false">
            <circle
              cx="21"
              cy="21"
              r="14"
              fill="rgba(255, 255, 255, 0.5)"
              stroke="currentColor"
              strokeWidth="3"
            />
            <line
              x1="31"
              y1="31"
              x2="45"
              y2="45"
              stroke="currentColor"
              strokeWidth="5"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* The rotating line is decoration and is kept away from assistive
          technology, which would otherwise be read a new sentence every three
          seconds. The one below it is the whole message, said once. */}
      <p className="feedback-wait-caption" key={caption} aria-hidden="true">
        {CAPTIONS[caption]}
      </p>

      <p className="feedback-wait-note" role="status">
        Das dauert meist weniger als eine Minute. Sobald es fertig ist, geht es
        automatisch weiter.
      </p>

      {/* Never a locked screen: the transcript is the one thing a training is
          guaranteed to leave behind, and for a call that was not stored it is
          the only copy there is (F-64). */}
      <button type="button" className="feedback-wait-skip" onClick={onDone}>
        Ohne Feedback weiter zum Protokoll
      </button>
    </div>
  );
}
