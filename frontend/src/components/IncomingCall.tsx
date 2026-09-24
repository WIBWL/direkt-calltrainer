import { useState, type CSSProperties } from "react";

import { RINGTONE_CYCLE_MS, useRingtone } from "../hooks/useRingtone";
import PersonaAvatar from "./PersonaAvatar";

/**
 * The phone ringing before an ordinary call (F-63): the Persona rang (`_casting`), so the
 * user accepts, which sends `session.activate` (ADR 0042). Not for a reverse (ADR 0070).
 * The ringtone is stoppable (WCAG 1.4.2) and remembered; the switch's target is 24px (2.5.8).
 */

/** Where the ringtone preference lives. Per browser, per person, and of no
 * interest to the server. */
const MUTED_KEY = "calltrainer.ringtoneMuted";

function loadMuted(): boolean {
  try {
    return window.localStorage.getItem(MUTED_KEY) === "1";
  } catch {
    return false; // private mode or blocked storage: ring, and forget the choice
  }
}

function saveMuted(muted: boolean) {
  try {
    window.localStorage.setItem(MUTED_KEY, muted ? "1" : "0");
  } catch {
    // see above; the toggle still works for this call
  }
}

/** The handset, as an arc with two thickened ends. Drawn rather than taken
 * from an icon set: it is two shapes, and this way nothing has to be vendored
 * for one glyph. */
function Handset({ declining = false }: { declining?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="incoming-handset">
      <g transform={declining ? "rotate(133 12 12)" : undefined}>
        <path
          d="M 6.4 17.6 Q 6.4 6.4 17.6 6.4"
          fill="none"
          stroke="currentColor"
          strokeWidth="3.6"
          strokeLinecap="round"
        />
        <circle cx="6.4" cy="17.6" r="3.1" fill="currentColor" />
        <circle cx="17.6" cy="6.4" r="3.1" fill="currentColor" />
      </g>
    </svg>
  );
}

export default function IncomingCall({
  personaName,
  personaAvatarUrl,
  onAccept,
  onDecline,
}: {
  personaName: string;
  /** `persona.avatar_url`; null falls back to the initials, as everywhere. */
  personaAvatarUrl: string | null;
  onAccept: () => void;
  onDecline: () => void;
}) {
  // Lazy initializer: read once on mount, not on every render.
  const [muted, setMuted] = useState(loadMuted);
  useRingtone(!muted);

  const muteLabel = muted ? "Klingelton einschalten" : "Klingelton ausschalten";

  const toggleSound = () => {
    setMuted((was) => {
      saveMuted(!was);
      return !was;
    });
  };

  return (
    <section className="incoming" aria-labelledby="incoming-title">
      {/* The shake and the rings run on the ringtone's own cycle, from the one
          place that number lives — and they run whether or not it is audible:
          a muted phone still buzzes. */}
      <div
        className="incoming-stage"
        style={{ "--ring-cycle": `${RINGTONE_CYCLE_MS}ms` } as CSSProperties}
      >
        {/* Behind the phone and purely visual: the sound it would be making. */}
        <div className="incoming-rings" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="incoming-phone">
          {/* The device's own hardware: the keys down its sides and the black
              pill in the display. Drawn because a phone without them reads as
              a blue rectangle with a name in it, which is what this was. */}
          <span
            className={`incoming-key incoming-key-silent${muted ? " is-silenced" : ""}`}
            aria-hidden="true"
          />
          <span className="incoming-key incoming-key-up" aria-hidden="true" />
          <span className="incoming-key incoming-key-down" aria-hidden="true" />
          <span className="incoming-key incoming-key-power" aria-hidden="true" />

          <div className="incoming-screen">
            <div className="incoming-island" aria-hidden="true" />

            {/* The portrait and the name, which is what a phone shows: not a
                caption saying that someone is calling. Who they *are* comes out
                in the call, which is the exercise. Zoomed to head and
                shoulders like the selection card's, because at 72px the whole
                half-body shot leaves a face too small to recognise. */}
            <PersonaAvatar
              name={personaName}
              src={personaAvatarUrl}
              className="incoming-avatar"
            />

            <p className="incoming-caller" id="incoming-title">
              {personaName}
            </p>

            <div className="incoming-actions">
              <span className="incoming-action">
                <button
                  type="button"
                  className="incoming-button incoming-decline"
                  onClick={onDecline}
                >
                  <Handset declining />
                </button>
                <span className="incoming-action-label">Ablehnen</span>
              </span>

              <span className="incoming-action">
                <button
                  type="button"
                  className="incoming-button incoming-accept"
                  onClick={onAccept}
                  // The visible label is under the button; the accessible name
                  // has to say what accepting starts.
                  aria-label="Anruf annehmen und Gespräch beginnen"
                >
                  <Handset />
                </button>
                <span className="incoming-action-label">Annehmen</span>
              </span>
            </div>
          </div>
        </div>

        {/* The silent switch's control; label and arrow are part of the target. A sibling
            of the phone, not a child, because the phone shakes and a bobbing label is
            unreadable. The name is on the button too (WCAG 2.5.3): the label is hidden
            on narrow screens, and a hidden <span> leaves the accessibility tree. */}
        <button
          type="button"
          className="incoming-mute-switch"
          onClick={toggleSound}
          aria-pressed={muted}
          aria-label={muteLabel}
          title={muteLabel}
        >
          <span className="incoming-mute-label" aria-hidden="true">
            {muteLabel}
          </span>

          <svg className="incoming-mute-arrow" viewBox="0 0 44 12" aria-hidden="true">
            <path
              d="M1 6 H39"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
            <path
              d="M33.5 1.8 L39.6 6 L33.5 10.2"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <p className="incoming-hint">
        Sobald Sie annehmen, meldet sich Ihr Gegenüber — reagieren Sie wie am Telefon.
      </p>
    </section>
  );
}
