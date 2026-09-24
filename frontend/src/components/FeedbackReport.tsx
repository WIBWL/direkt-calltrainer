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

/**
 * User utterances needed before the follow-up and reverse offers appear: a call hung up
 * after a sentence has nothing to build from. Counts the User's own rows only. The routes
 * refuse under `MIN_USER_UTTERANCES` (`backend/api/sessions.py`, pinned by `tests/test_reverse.py`).
 */
const MIN_USER_TURNS = 3;

/**
 * The wrap-up itself, given fetched data, without the post-call notices, so the history's
 * page can render it too. Renders nothing without a wrap-up: what to say instead differs
 * per screen. The follow-up/reverse offers (F-60, F-61) are props for the same reason.
 */
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
  // The catalogue, for naming the goal a point was tagged with. Null while it
  // has not loaded or failed to, and the tags are then simply absent.
  const { focus: picked } = useFocusContext();
  if (!feedback) return null;

  const outline = wrapUpOutline(feedback, turns, picked?.goals ?? []);
  const improvements = outline.improvements;
  const spokenTurns = turns.filter((turn) => turn.speaker === "user").length;
  const longEnough = spokenTurns >= MIN_USER_TURNS;

  // Built here so "is there anything to offer?" is asked once and the row never
  // appears empty. Only where the wrap-up named improvement points: those are the
  // follow-up's whole input, and the route refuses without them (ADR 0069).
  const followUpOffer =
    followUp && longEnough && improvements.length > 0 ? (
      <FollowUp
        scenario={detail.follow_up}
        personaId={detail.persona_id}
        sessionId={detail.session_id}
        {...followUp}
      />
    ) : null;
  // No condition on the points: a reverse copies the case that was played, so
  // it is available for any call that was actually conducted — except a reverse
  // itself, which is already the other way round (ADR 0070).
  const reverseOffer =
    onReverse && longEnough && !detail.reverse ? (
      <Reverse sessionId={detail.session_id} onReverse={onReverse} />
    ) : null;

  // No meta row here any more: which case, which partner and which side the
  // User was on describe the *call*, not the wrap-up, and a Session whose
  // wrap-up never got written still has all three. `FeedbackScreen` shows them
  // under the title of both screens instead.
  return (
    <>
      <section className="feedback-section feedback-summary-section">
        <div className="feedback-box feedback-summary-card">
          <SectionHeading eyebrow="QUALITATIVE EINORDNUNG" title="Zusammenfassung" />
          <p className="feedback-summary-text">{outline.summary}</p>
        </div>
      </section>

      <div className="feedback-details">
        <PointList
          eyebrow="STÄRKEN"
          title="Das gelang gut"
          points={outline.strengths}
          tone="success"
        />

        <PointList
          eyebrow="WEITERENTWICKELN"
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

      {/* Last: what to do after reading. The two offers sit side by side as alternatives;
          either may be absent, and the other then takes the full width. The next-call
          offers (F-64) go under them, or stand alone. `next` is an element even when it
          renders nothing, so it cannot decide whether the heading appears. */}
      {followUpOffer || reverseOffer ? (
        <section className="feedback-section">
          <SectionHeading eyebrow="WIE ES WEITERGEHT" title="Nächste Schritte" />
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

/**
 * F-42's register block: the model's reading as the finding itself, and behind the "i"
 * what it rests on and cannot tell (ADR 0056: the phase boundaries are the model's guess).
 */
function PhaseLanguage({ text }: { text: string }) {
  return (
    <section className="feedback-section feedback-phase-card">
      <SectionHeading eyebrow="GESPRÄCHSFÜHRUNG" title="Phasengerechte Sprache" />

      <div className="feedback-box">
        <p className="feedback-phase-text">{text}</p>

        <p className="feedback-phase-note">
          Warm einsteigen, sachlich am Anliegen arbeiten, warm abschließen.
        </p>

        <InfoDetails label="Warum diese Reihenfolge">
          {/* A list, not prose: each phase asks for a different register for a
              different reason, and three reasons run together in a paragraph
              read as one. */}
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
  eyebrow,
  title,
  points,
  tone,
}: {
  eyebrow: string;
  title: string;
  points: OutlinePoint[];
  tone: "success" | "danger";
}) {
  // Null on a screen with no transcript, and then the moment stays the plain
  // text it has always been (see TranscriptFocus.tsx).
  const focus = useTranscriptFocus();

  if (points.length === 0) return null;
  return (
    <section className={`feedback-section feedback-point-section ${tone}`}>
      <div className={`feedback-box feedback-point-card ${tone}`}>
        <SectionHeading
          eyebrow={eyebrow}
          title={title}
          tone={tone}
          icon={tone === "success" ? "✓" : "!"}
        />

        <div className="feedback-point-list">
          {points.map((point, i) => {
            const at = point.offsetMs;
            return (
              <div className="feedback-point-item" key={i}>
                {/* The moment this was written about, as something to press.
                  A timestamp alone is checkable only by somebody who still
                  remembers the call; the line it names sits collapsed a little
                  further down, and one press opens it there. */}
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
                {/* The focus goal the wrap-up filed this point under (ADR 0080), as an eyebrow
                  above the sentence so it reads as a heading. Shown for every tagged
                  point, not only the User's own five. */}
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
