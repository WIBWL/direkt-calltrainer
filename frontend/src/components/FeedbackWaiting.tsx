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
 * What the wait is actually spent on, roughly in order. Light in tone, but every line
 * is true of what the worker is doing, which keeps it from reading as filler.
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
 * How long this screen waits before handing over regardless. `useSessionFeedback` polls
 * for ten minutes, too long for a screen holding nothing else; the poll carries on behind
 * the post-call screen, where the wrap-up appears when it lands.
 */
const WAIT_LIMIT_MS = 120_000;

/**
 * The wait between hanging up and the wrap-up the worker writes (F-09/F-10, ADR 0049).
 * Under `prefers-reduced-motion` the scene stands still rather than being skipped. Never
 * shown for an unstored Session (ADR 0066): App.tsx enters it only with a `sessionId`.
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
