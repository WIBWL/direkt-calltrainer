import { useEffect, useState, type CSSProperties } from "react";

import type { FeedbackState } from "../hooks/useSessionFeedback";

/** Uneven: an even row is a loading indicator, an uneven one somebody talking. */
const BARS = [26, 52, 74, 44, 96, 62, 34, 70, 40, 58, 28];

const CAPTION_MS = 3400;

/** Every line is true of what the worker is doing. */
const CAPTIONS = [
  "Das Gespräch wird abgetippt …",
  "Ihre Sprechpausen werden vermessen …",
  "Ähms werden wohlwollend überhört …",
  "Ihre Fragen werden gezählt …",
  "Es wird nach Ihren besten Momenten gesucht …",
  "Die Zusammenfassung wird geschrieben …",
];

/** The poll carries on behind the post-call screen. */
const WAIT_LIMIT_MS = 120_000;

/** The wait for the worker's wrap-up (ADR 0049). Never for an unstored Session (ADR 0066). */
export default function FeedbackWaiting({
  state,
  onDone,
}: {
  state: FeedbackState;
  /** The wrap-up settled, or the User would rather read the transcript. */
  onDone: () => void;
}) {
  const [caption, setCaption] = useState(0);

  // Only "loading" still waits; failed or unstored has settled.
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

      {/* Hidden from assistive technology, which would read a new sentence every three seconds. */}
      <p className="feedback-wait-caption" key={caption} aria-hidden="true">
        {CAPTIONS[caption]}
      </p>

      <p className="feedback-wait-note" role="status">
        Das dauert meist weniger als eine Minute. Sobald es fertig ist, geht es
        automatisch weiter.
      </p>

      {/* Never locked: for an unstored call the transcript is the only copy (F-64). */}
      <button type="button" className="feedback-wait-skip" onClick={onDone}>
        Ohne Feedback weiter zum Protokoll
      </button>
    </div>
  );
}
