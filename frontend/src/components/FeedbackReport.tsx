import type { ReactNode } from "react";

import { useFocusContext } from "../FocusContext";
import type { SessionDetail } from "../protocol";
import type { ReverseScenario } from "../scenarioLibrary";
import { wrapUpOutline, type OutlinePoint } from "../utils/reportOutline";
import { formatOffset } from "../utils/time";
import InfoDetails from "./InfoDetails";
import MetricSection from "./MetricSection";
import { FollowUp, Reverse, type FollowUpActions } from "./NextSteps";
import SectionHeading from "./SectionHeading";
import { useTranscriptFocus } from "./TranscriptFocus";

/** User rows needed before the follow-up and reverse offers; matches the routes'
 * `MIN_USER_UTTERANCES` (pinned by backend/tests/test_reverse.py). */
const MIN_USER_TURNS = 3;

/** The wrap-up alone, so the history's page can render it too. Renders nothing without one. */
export default function FeedbackReport({
  detail,
  followUp,
  onReverse,
  next,
}: {
  detail: SessionDetail;
  followUp?: FollowUpActions | undefined;
  onReverse?: ((reverse: ReverseScenario) => void) | undefined;
  next?: ReactNode;
}) {
  const { feedback, measurements, turns } = detail;
  // Null while loading or failed; the tags are then absent.
  const { focus: picked } = useFocusContext();
  if (!feedback) return null;

  const outline = wrapUpOutline(feedback, turns, picked?.goals ?? []);
  const improvements = outline.improvements;
  const spokenTurns = turns.filter((turn) => turn.speaker === "user").length;
  const longEnough = spokenTurns >= MIN_USER_TURNS;

  // Only with improvement points, the follow-up's whole input (ADR 0069).
  const followUpOffer =
    followUp && longEnough && improvements.length > 0 ? (
      <FollowUp
        scenario={detail.follow_up}
        personaId={detail.persona_id}
        sessionId={detail.session_id}
        {...followUp}
      />
    ) : null;
  // Any conducted call except a reverse itself (ADR 0070).
  const reverseOffer =
    onReverse && longEnough && !detail.reverse ? (
      <Reverse sessionId={detail.session_id} onReverse={onReverse} />
    ) : null;

  return (
    <>
      <section className="feedback-section feedback-summary-section">
        <div className="feedback-box feedback-summary-card">
          <SectionHeading title="Zusammenfassung" />
          <p className="feedback-summary-text">{outline.summary}</p>
        </div>
      </section>

      <div className="feedback-details">
        <PointList
          title="Das gelang gut"
          points={outline.strengths}
          tone="success"
        />

        <PointList
          title="Das können Sie verbessern"
          points={improvements}
          tone="danger"
        />
      </div>

      {outline.phaseLanguage && <PhaseLanguage text={outline.phaseLanguage} />}

      <MetricSection
        measurements={measurements}
        findings={detail.findings}
        notes={detail.metric_notes}
        sessionId={detail.session_id}
        segments={detail.segments}
      />

      {/* The two offers side by side, either may be absent; the next-call offers (F-64) under them. */}
      {followUpOffer || reverseOffer ? (
        <section className="feedback-section">
          <SectionHeading title="Nächste Schritte" />
          <div className="next-steps">
            {followUpOffer}
            {reverseOffer}
          </div>
          {next}
        </section>
      ) : (
        next
      )}
    </>
  );
}

/** F-42's register block; the phase boundaries are the model's guess (ADR 0056). */
function PhaseLanguage({ text }: { text: string }) {
  return (
    <section className="feedback-section feedback-phase-card">
      <SectionHeading title="Phasengerechte Sprache" />

      <div className="feedback-box">
        <p className="feedback-phase-text">{text}</p>

        <p className="feedback-phase-note">
          Warm einsteigen, sachlich am Anliegen arbeiten, warm abschließen.
        </p>

        <InfoDetails label="Warum diese Reihenfolge">
          {/* A list: three reasons run together in prose read as one. */}
          <dl className="feedback-phase-phases">
            <dt>Einstieg</dt>
            <dd>
              warm und persönlich. Hier entscheidet sich, ob Ihr Gegenüber sich ernst
              genommen fühlt.
            </dd>

            <dt>Anliegen</dt>
            <dd>sachlich und präzise. Jetzt zählt, dass seine Zeit respektiert wird.</dd>

            <dt>Abschluss</dt>
            <dd>
              wieder warm. Das Ende prägt, wie das ganze Gespräch in Erinnerung bleibt.
            </dd>
          </dl>

          <p>
            Aus der wissenschaftlichen Studie von Packard, Li und Berger (2024), belegt
            durch echte Servicegespräche. Kein Messwert: Die Phasengrenzen schätzt das
            Sprachmodell selbst.
          </p>
          <p className="feedback-phase-source">
            Packard, Li &amp; Berger (2024), Journal of Consumer Research 51 (3);
            Kahneman et al. (1993), Psychological Science 4 (6).
          </p>
        </InfoDetails>
      </div>
    </section>
  );
}

function PointList({
  title,
  points,
  tone,
}: {
  title: string;
  points: OutlinePoint[];
  tone: "success" | "danger";
}) {
  // Null without a transcript (TranscriptFocus.tsx).
  const focus = useTranscriptFocus();

  if (points.length === 0) return null;
  return (
    <section className={`feedback-section feedback-point-section ${tone}`}>
      <div className={`feedback-box feedback-point-card ${tone}`}>
        <SectionHeading
          title={title}
          tone={tone}
          icon={tone === "success" ? "✓" : "!"}
        />

        <div className="feedback-point-list">
          {points.map((point, i) => {
            const at = point.offsetMs;
            return (
              <div className="feedback-point-item" key={i}>
                {/* One press opens the transcript at the line. */}
                {at !== null &&
                  (focus ? (
                    <button
                      type="button"
                      className="feedback-point-time feedback-point-jump"
                      onClick={() => focus.reveal(at)}
                      aria-label={`Die Stelle bei ${formatOffset(at)} im Transkript zeigen`}
                    >
                      {formatOffset(at)}
                    </button>
                  ) : (
                    <span className="feedback-point-time">{formatOffset(at)}</span>
                  ))}
                {/* The goal the point was filed under (ADR 0080), as an eyebrow. */}
                <div className="feedback-point-body">
                  {point.goal && <span className="feedback-point-goal">{point.goal}</span>}
                  <p>{point.text}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
