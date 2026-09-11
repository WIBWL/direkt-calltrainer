import { useState, type ReactNode } from "react";

import type { TranscriptEntry } from "../protocol";
import { downloadTranscriptPdf } from "../utils/transcriptPdf";
import { SectionHeading } from "./FeedbackView";

interface TranscriptViewProps {
  transcript: TranscriptEntry[];
  personaName: string;
  onRestart: () => void;
  /** The AI-generated wrap-up, shown above the log. Passed in rather than
   * fetched here, so this component stays the plain Transcript it is. */
  feedback?: ReactNode;
  /** For a Zufallsszenario (F-62): which case was drawn, told now that the
   * call is over. Null for a Scenario the User chose — naming it back to them
   * would be telling them what they already picked. */
  revealedScenario?: string | null;
}

/** The post-call screen: the wrap-up, and the Gesprächsprotokoll as a file to
 * take away (F-64).
 *
 * The log used to be printed out here in full. It is a document rather than a
 * page section — it is read closely or not at all, it is the one thing worth
 * keeping from a training that may not have been stored, and at length it
 * pushed everything that comments on it off the screen. So it is offered as a
 * PDF instead, built in the browser from the same lines this screen already
 * holds (see `utils/transcriptPdf.ts`).
 *
 * The server flattens the exchanges, so the ordering lives in one place rather
 * than being reconstructed here (ADR 0051). */
export default function TranscriptView({
  transcript,
  personaName,
  onRestart,
  feedback,
  revealedScenario,
}: TranscriptViewProps) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const download = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await downloadTranscriptPdf({ transcript, personaName });
    } catch (e) {
      console.debug("[transcript pdf] failed", e);
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

        {/* The answer to the question the User has been carrying since the
            call began. Above the wrap-up, because every line of that already
            assumes it. */}
        {revealedScenario && (
          <p className="scenario-reveal">
            Ihr Zufallsszenario war: <strong>{revealedScenario}</strong>
          </p>
        )}
      </div>
      <section className="feedback-section">
        <SectionHeading
          eyebrow="GESPRÄCH IM DETAIL"
          title="Vollständiges Transkript"
          aside={`${transcript.length} Beiträge`}
        />

        <div className="feedback-box transcript-download">
          {transcript.length === 0 ? (
            <p className="transcript-empty">Es wurden keine Beiträge aufgezeichnet.</p>
          ) : (
            <>
              <p className="transcript-download-lead">
                Das vollständige Protokoll dieses Gesprächs — jeder Beitrag mit Zeitmarke,
                in der Reihenfolge, in der er gesprochen wurde.
              </p>

              <button
                type="button"
                className="follow-up-button"
                disabled={busy}
                onClick={download}
              >
                {busy ? "PDF wird erstellt …" : "Transkript als PDF herunterladen"}
              </button>

              {failed && (
                <p className="follow-up-error">
                  Das PDF konnte nicht erstellt werden. Bitte versuchen Sie es erneut.
                </p>
              )}

              {/* Said because it is true and because it is easy to forget once
                  a file is on the desktop: this one carries what was said. */}
              <p className="transcript-download-note">
                Die Datei wird auf Ihrem Gerät erzeugt und nicht hochgeladen. Sie enthält den
                gesprochenen Inhalt des Trainings — bewahren Sie sie entsprechend auf.
              </p>
            </>
          )}
        </div>
      </section>


      {feedback}

      <div className="feedback-actions">
        <button className="back-to-start-button" type="button" onClick={onRestart}>
          Zur Startseite
        </button>
      </div>
    </>
  );
}
