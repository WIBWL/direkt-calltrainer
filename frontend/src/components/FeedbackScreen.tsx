import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";

import { useFocusContext } from "../FocusContext";
import { useAccount } from "../hooks/useAccount";
import type { SessionDetail, SessionTurn, TranscriptEntry } from "../protocol";
import { downloadFeedbackPdf } from "../utils/feedbackPdf";
import { initialsOf } from "../utils/initials";
import { prefersReducedMotion } from "../utils/motion";
import { callMeta } from "../utils/reportOutline";
import { formatOffset } from "../utils/time";
import { TranscriptFocusProvider } from "./TranscriptFocus";

interface FeedbackScreenProps {
  transcript: TranscriptEntry[];
  personaName: string;
  /** The case that was played, named in the meta row under the title — which
   * is where a random Scenario (F-62) is revealed like any other case too —
   * and in the PDF. */
  scenarioName?: string | null;
  /** The rendered wrap-up: `FeedbackReport`, or whatever the screen says in
   * its place. Passed in rather than fetched here, because the two screens
   * come by it differently — one polls for it, one reads it once. */
  feedback?: ReactNode;
  /** The same wrap-up as data, for the file: the report above is a rendered
   * node and cannot be read back out of one. Null while it is still being
   * generated, and for a call that was never stored (ADR 0066) — the download
   * is then the protocol alone, and says so. */
  detail?: SessionDetail | null;
  /** What leads away from this screen, first in the actions row: preparation
   * after a call, back to the profile in the history. The one thing the two
   * screens are allowed to differ in. */
  actions?: ReactNode;
  /** Anything that belongs *under* the transcript — the history's delete. */
  children?: ReactNode;
}

/**
 * The feedback screen: the wrap-up, the whole of it as a file to take away
 * (F-64), and the Transcript either inside that file or read here.
 *
 * Used by both screens that show a wrap-up — after a call, and a past training
 * opened from the profile — so they cannot drift apart. They did: one report
 * under two titles, with the history's transcript a plain list where the
 * post-call screen had a panel that opens. Only the actions row still differs,
 * which is what `actions` and `children` are for.
 *
 * The download is the *feedback*, not the log: everything the page shows, in
 * its order, transcript last (`utils/feedbackPdf.ts`). For a training run
 * without consent that file is the only copy of any of it (ADR 0066).
 *
 * The transcript stays collapsed beside the download rather than printed in
 * full, which pushed everything commenting on it off the screen — a question
 * about one line is not worth a file, and a file to check a detail is a detour.
 *
 * The server flattens the exchanges, so the ordering lives in one place rather
 * than being reconstructed here (ADR 0051).
 */
export default function FeedbackScreen({
  transcript,
  personaName,
  scenarioName,
  feedback,
  detail,
  actions,
  children,
}: FeedbackScreenProps) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  // Which line of the transcript a wrap-up point pointed at, so it can be
  // brought into view and marked while it is read (see TranscriptFocus.tsx).
  const [focused, setFocused] = useState<number | null>(null);
  const logId = useId();
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  // The User's own initials on their lines, from the ID token — the Persona is
  // the one with a fixed name here, and "D" for "Du" named nobody.
  const account = useAccount();
  // Handed to the file so a point there names its goal as it does on the page.
  const { focus: picked } = useFocusContext();
  const meta = callMeta(personaName, scenarioName, detail?.reverse);

  // What the file is called on the button, and what it will hold: without a
  // wrap-up there is no feedback to download, only the protocol. The two
  // labels rather than one that is sometimes a promise — a User who presses a
  // button offering feedback and gets a bare transcript was misled.
  const complete = Boolean(detail?.feedback);

  // One press on a point's timestamp does two things, and the order matters:
  // the panel has to be open before the line it holds can be scrolled to, so
  // the scrolling waits for the render in the effect below.
  const reveal = useCallback((offsetMs: number) => {
    setExpanded(true);
    setFocused(offsetMs);
  }, []);

  const focus = useMemo(() => ({ reveal, focused }), [reveal, focused]);

  useEffect(() => {
    if (focused === null || !expanded) return;
    const line = transcriptRef.current?.querySelector(`[data-offset="${focused}"]`);
    // `block: "center"` rather than the default: the line otherwise lands under
    // the sticky header, and a reader who pressed a button and saw the page
    // jump to nothing would take it for a broken control.
    line?.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }, [focused, expanded]);

  const download = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await downloadFeedbackPdf({
        transcript,
        personaName,
        scenarioName,
        detail: detail ?? null,
        goals: picked?.goals ?? [],
      });
    } catch (e) {
      console.debug("[feedback pdf] failed", e);
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const body = (
    <>
      <div className="feedback-intro">
        <div className="eyebrow">TRAINING ABGESCHLOSSEN</div>
        <h1 className="feedback-title">Ihr Gesprächsfeedback</h1>
      </div>

      {/* Which training this was, directly under the title. It sits here
          rather than in the report, because it describes the call and not the
          wrap-up: a Session whose wrap-up never got written still has a case
          and a partner, and the history used to be the only screen that said
          so. Which side the User was on is part of that — the transcript below
          reads very differently depending on it (ADR 0070). */}
      <div className="feedback-meta" aria-label="Trainingsdetails">
        {meta.scenario && <span>{meta.scenario}</span>}
        {meta.scenario && (
          <span className="feedback-meta-separator" aria-hidden="true">
            ·
          </span>
        )}
        <span>{meta.reversal ? `Rollentausch: ${meta.reversal}` : meta.partner}</span>
      </div>

      {feedback}

      {/* All of them are what to do once the reading is done, so they share the
          row rather than the log having a section of its own. It had one: a box
          explaining what a transcript is, above a report that comments on it.
          The buttons say what they do. Reading comes before keeping, so the
          panel sits to the left of the file. */}
      <div className="feedback-actions">
        {actions}

        {transcript.length > 0 && (
          <>
            <button
              type="button"
              className="back-to-start-button"
              aria-expanded={expanded}
              aria-controls={logId}
              onClick={() => setExpanded((open) => !open)}
            >
              {expanded ? "Transkript einklappen" : "Transkript ausklappen"}
            </button>

            <button
              type="button"
              className="back-to-start-button"
              disabled={busy}
              onClick={download}
            >
              {busy
                ? "PDF wird erstellt …"
                : complete
                  ? "Gesprächsfeedback herunterladen"
                  : "Transkript als PDF herunterladen"}
            </button>
          </>
        )}
      </div>

      {failed && (
        <p className="follow-up-error transcript-download-error">
          Das PDF konnte nicht erstellt werden. Bitte versuchen Sie es erneut.
        </p>
      )}

      {/* Below the button that opened it, so the panel grows out of its own
          control rather than appearing somewhere the press did not point. Not
          rendered at all while closed: the lines are the longest thing on this
          screen, and an empty container would still take the page's scroll
          height with it. */}
      {expanded && transcript.length > 0 && (
        <section className="feedback-transcript-section" id={logId}>
          <div className="feedback-transcript-heading">
            <div>
              <div className="feedback-transcript-eyebrow">GESPRÄCH IM DETAIL</div>
              <h2 className="feedback-transcript-title">Vollständiges Transkript</h2>
            </div>

            <span className="feedback-transcript-count">{transcript.length} Beiträge</span>
          </div>

          <div className="feedback-transcript-card" ref={transcriptRef}>
            {transcript.map((entry, i) => (
              <div
                className={`transcript-line${entry.offset_ms === focused ? " is-focused" : ""}`}
                key={i}
                data-offset={entry.offset_ms}
              >
                <span className="transcript-time">{formatOffset(entry.offset_ms)}</span>

                {/* Decorative: the name is spelled out beside it. */}
                <span className="transcript-avatar" aria-hidden="true">
                  {entry.speaker === "user" ? account.initials : initialsOf(personaName)}
                </span>

                <div className="transcript-content">
                  <div className="transcript-speaker">
                    {entry.speaker === "user" ? "Du" : personaName}
                  </div>

                  <p className="transcript-text">{entry.text}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {children}
    </>
  );

  // The points may point at a line only while there is one to point at. On a
  // Session with no stored transcript they keep the plain timestamp they have
  // always carried, rather than a control that would open nothing.
  return transcript.length > 0 ? (
    <TranscriptFocusProvider value={focus}>{body}</TranscriptFocusProvider>
  ) : (
    body
  );
}

/** The stored utterances as the screen reads them. One row per speaker either
 * way (ADR 0051), so this is a rename and not a reshaping — it exists because
 * a call that has just ended has its lines from the socket and a past one from
 * the database, and the screen should not have to know which. */
export function transcriptFromTurns(turns: SessionTurn[]): TranscriptEntry[] {
  return turns.map((turn) => ({
    speaker: turn.speaker,
    text: turn.transcript,
    offset_ms: turn.start_offset_ms,
  }));
}
