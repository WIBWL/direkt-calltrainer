import { useState, type CSSProperties } from "react";

import { RINGTONE_CYCLE_MS, useRingtone } from "../hooks/useRingtone";
import PersonaAvatar from "./PersonaAvatar";

/** The phone ringing before an ordinary call (F-63): accepting sends
 * `session.activate` (ADR 0042) and the user speaks first (ADR 0110). The
 * ringtone is stoppable (WCAG 1.4.2) and remembered. */

/** Per browser; of no interest to the server. */
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
  personaAvatarUrl: string | null;
  onAccept: () => void;
  onDecline: () => void;
}) {
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
      {/* On the ringtone's cycle, audible or not: a muted phone still buzzes. */}
      <div
        className="incoming-stage"
        style={{ "--ring-cycle": `${RINGTONE_CYCLE_MS}ms` } as CSSProperties}
      >
        <div className="incoming-rings" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="incoming-phone">
          <span
            className={`incoming-key incoming-key-silent${muted ? " is-silenced" : ""}`}
            aria-hidden="true"
          />
          <span className="incoming-key incoming-key-up" aria-hidden="true" />
          <span className="incoming-key incoming-key-down" aria-hidden="true" />
          <span className="incoming-key incoming-key-power" aria-hidden="true" />

          <div className="incoming-screen">
            <div className="incoming-island" aria-hidden="true" />

            {/* Zoomed to head and shoulders: at 72px the half-body shot is too small. */}
            <PersonaAvatar
              name={personaName}
              src={personaAvatarUrl}
              className="incoming-avatar"
            />

            <h1 className="incoming-caller" id="incoming-title">
              {personaName}
            </h1>

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
                  aria-label="Anruf annehmen und Gespräch beginnen"
                >
                  <Handset />
                </button>
                <span className="incoming-action-label">Annehmen</span>
              </span>
            </div>
          </div>
        </div>

        {/* A sibling of the phone, which shakes. The name is on the button too
            (WCAG 2.5.3): the label is hidden on narrow screens. */}
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
        Sobald Sie annehmen, beginnt das Telefonat. Melden Sie sich beim Anrufer mit einer Begrüßung.
      </p>
    </section>
  );
}
