import { useState, type CSSProperties } from "react";

import { RINGTONE_CYCLE_MS, useRingtone } from "../hooks/useRingtone";

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

/** Up to two letters, from a name that is a Persona's and therefore short.
 * Falls back to the first character rather than to a placeholder: a blank
 * circle on a ringing phone reads as something failing to load. */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const letters = parts.slice(0, 2).map((p) => p.charAt(0));
  return letters.join("").toUpperCase();
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
  onAccept,
  onDecline,
}: {
  personaName: string;
  onAccept: () => void;
  onDecline: () => void;
}) {
  // Lazy initializer: read once on mount, not on every render.
  const [muted, setMuted] = useState(loadMuted);
  useRingtone(!muted);

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
          <span className="incoming-key incoming-key-silent" aria-hidden="true" />
          <span className="incoming-key incoming-key-up" aria-hidden="true" />
          <span className="incoming-key incoming-key-down" aria-hidden="true" />
          <span className="incoming-key incoming-key-power" aria-hidden="true" />

          <div className="incoming-screen">
            <div className="incoming-island" aria-hidden="true" />

            {/* The name and nothing else: a real phone shows who is calling,
                not a caption saying that someone is. Who they are comes out in
                the call, which is the exercise. */}
            <div className="incoming-avatar" aria-hidden="true">
              {initials(personaName)}
            </div>

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
      </div>

      <p className="incoming-hint">
        Sobald Sie annehmen, meldet sich Ihr Gegenüber — reagieren Sie wie am Telefon.
      </p>

      <button type="button" className="incoming-mute" onClick={toggleSound} aria-pressed={muted}>
        {muted ? "Klingelton einschalten" : "Klingelton ausschalten"}
      </button>
    </section>
  );
}
