import { useState, type CSSProperties } from "react";

import { RINGTONE_CYCLE_MS, useRingtone } from "../hooks/useRingtone";
import PersonaAvatar from "./PersonaAvatar";

/**
 * The phone ringing between the microphone check and an ordinary call (F-63).
 *
 * The call has to be *accepted*, not merely arrived at: in an ordinary Session
 * the Persona is the one who rang (`_casting` in `session/prompting.py` — it
 * has a concern and the user is the support or sales side it reached), so
 * picking up is what the user actually does, and the screen that says so is
 * the last thing before they have to say hello.
 *
 * It is also the only screen between the check and the call where nothing is
 * happening yet: the Session is connected and the opening line is generated
 * and waiting (ADR 0042), held back until `session.activate`. Accepting is
 * what sends it. So the wait is real rather than staged — the Persona is
 * genuinely on the line.
 *
 * Not shown for a reverse (ADR 0070): there the user is the caller, and a
 * screen asking them to take an incoming call would have the roles the wrong
 * way round on the one feature that is about roles.
 *
 * The ringtone can be switched off, and the switch is not a nicety: sound that
 * starts by itself and runs longer than three seconds has to be stoppable
 * (WCAG 2.1 SC 1.4.2), and this project publishes an accessibility statement.
 * The choice is remembered, because someone who turns it off in an open-plan
 * office does not want to turn it off again before every call.
 *
 * It is the phone's own silent switch rather than a link under the device —
 * the place a person already reaches for, and one fewer thing beside a screen
 * that is meant to read as a phone and not as a page about one. The hit area
 * is much larger than the sliver it draws, because the sliver is 3px wide and
 * a target has to be 24px (WCAG 2.5.8).
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

        {/* The silent switch's control: the label and the arrow are the target
            as much as the switch is, which is what makes a 3px sliver
            clickable without drawing it any bigger.

            A sibling of the phone rather than a child of it, because the phone
            shakes: 200px out from its centre, a 2° tilt swings text by about
            7px, and a label that bobs is a label nobody reads. The sliver it
            points at stays inside the device, where it belongs.

            The name is on the button as well as on screen — the same words, so
            WCAG 2.5.3 is satisfied either way — because the label is hidden on
            narrow screens where the arm does not fit, and a hidden <span> takes
            its text out of the accessibility tree with it. */}
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
