import { useId, useState, type ReactNode } from "react";

import { useAccount } from "../hooks/useAccount";
import type { SessionDetail, SessionTurn, TranscriptEntry } from "../protocol";
import { downloadFeedbackPdf } from "../utils/feedbackPdf";
import { formatOffset } from "../utils/time";

interface FeedbackScreenProps {
  transcript: TranscriptEntry[];
  personaName: string;
  /** The case that was played, named in the meta row under the title — which
   * is where a Zufallsszenario (F-62) is revealed like any other case too —
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
  /** What leads away from this screen, first in the actions row: "Zur
   * Startseite" after a call, "Zurück zum Profil" in the history. The one
   * thing the two screens are allowed to differ in. */
  actions?: ReactNode;
  /** Anything that belongs *under* the transcript — the history's delete. */
  children?: ReactNode;
}

/**
 * The feedback screen: the wrap-up, the whole of it as a file to take away
 * (F-64), and the Gesprächsprotokoll either inside that file or read here.
 *
 * Used by both screens that show a wrap-up — the one after a call and the one
 * a past training opens from the profile — so that they cannot drift apart.
 * They did: the same report sat under two different titles, and the history's
 * transcript was a plain list where the post-call screen had a panel that
 * opens. What still differs is the buttons in the actions row, which is what
 * `actions` and `children` are for, and nothing else.
 *
 * The download is the *feedback*, not the log: everything the page shows, in
 * the page's own order, with the transcript last (see `utils/feedbackPdf.ts`).
 * It began as the protocol alone, which was the smaller half of what a User
 * would want to keep — and for a training run without consent the file is the
 * only copy of any of it (ADR 0066).
 *
 * The log itself stays a document rather than a page section: it is read
 * closely or not at all, and printed out in full it pushed everything that
 * comments on it off the screen. So it is *collapsed* beside the download: a
 * question about one line is not worth a file, and a file the User has to open
 * to check a detail is a detour.
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
  const logId = useId();
  // The User's own initials on their lines, from the ID token — the Persona is
  // the one with a fixed name here, and "D" for "Du" named nobody.
  const account = useAccount();

  // What the file is called on the button, and what it will hold: without a
  // wrap-up there is no feedback to download, only the protocol. The two
  // labels rather than one that is sometimes a promise — a User who presses
  // "Gesprächsfeedback herunterladen" and gets a bare transcript was misled.
  const complete = Boolean(detail?.feedback);

  const download = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await downloadFeedbackPdf({
        transcript,
        personaName,
        scenarioName,
        feedback: detail?.feedback ?? null,
        measurements: detail?.measurements ?? [],
        turns: detail?.turns ?? [],
      });
    } catch (e) {
      console.debug("[feedback pdf] failed", e);
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
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
        {scenarioName && <span>{scenarioName}</span>}
        {scenarioName && (
          <span className="feedback-meta-separator" aria-hidden="true">
            ·
          </span>
        )}
        <span>
          {detail?.reverse ? `Rollentausch: Sie riefen an, ${personaName} nahm ab` : personaName}
        </span>
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

          <div className="feedback-transcript-card">
            {transcript.map((entry, i) => (
              <div className="transcript-line" key={i}>
                <span className="transcript-time">{formatOffset(entry.offset_ms)}</span>

                {/* Decorative: the name is spelled out beside it. */}
                <span className="transcript-avatar" aria-hidden="true">
                  {entry.speaker === "user"
                    ? account.initials
                    : personaName
                        .trim()
                        .split(/\s+/)
                        .filter(Boolean)
                        .map((part) => part.charAt(0).toUpperCase())
                        .slice(0, 2)
                        .join("")}
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
