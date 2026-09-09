import { useState } from "react";

import { ApiError } from "../api";
import type {
  FeedbackPoint,
  Measurement,
  SessionDetail,
  SessionTurn,
} from "../protocol";
import { formatOffset } from "../utils/time";
import { useSessionFeedback } from "../hooks/useSessionFeedback";
import {
  createFollowUp,
  createReverse,
  type FollowUpCard,
  type ReverseScenario,
} from "../scenarioLibrary";
import InfoDetails from "./InfoDetails";
import LoudnessCourse from "./LoudnessCourse";

/** What a screen can do with the follow-up Scenario (F-60): open it in the
 * editor, or start it as the next call. Both belong to whoever owns the screen,
 * so they are passed in — the post-call screen starts the call itself, the
 * history hands the pairing to the training flow.
 *
 * `onStart` gets the Persona too: the follow-up is played against the same
 * partner as the training it came out of, so there is nothing left to choose.
 *
 * `onCreated` fires once the User has asked for one and it has been written
 * (ADR 0069's amendment). The card renders from the answer either way; this is
 * for the screen's own copy of the library, which does not hold the new row
 * yet and is what "Starten" reads its names off. */
export interface FollowUpActions {
  onEdit: (scenarioId: string) => void;
  onStart: (scenarioId: string, personaId: string) => void;
  onCreated?: (() => void) | undefined;
}

/** How many decimals a metric reads naturally in. Counts are whole things;
 * seconds and percentages are not. */
const DECIMALS: Record<string, number> = { questions: 0, word_count: 0, pace: 0, talk_share: 0 };

/** Everything that is not a finished wrap-up is a one-line notice. There is
 * no entry for "ready": the hook reports it only once feedback is present. */
const NOTICE: Record<string, string> = {
  loading: "Das Feedback wird erstellt – einen Moment bitte.",
  missing: "Für dieses Gespräch wurde kein Feedback gespeichert.",
  failed:
    "Das Feedback konnte nicht erstellt werden. Das Gesprächsprotokoll unten ist davon nicht betroffen.",
};

/**
 * The post-call wrap-up (F-09/F-10/F-53): the narrative the model wrote, and
 * the statistics it was written from.
 *
 * The two are shown together deliberately. ADR 0004 makes the qualitative text
 * the feedback itself, and ADR 0049 keeps every number out of the model's
 * hands — so the figures here are the evidence behind the text, never a score.
 * Each one describes the whole call rather than a single utterance (ADR 0051).
 *
 * The phase block (F-42) sits below the figures on purpose: it is the one part
 * of the wrap-up that is about a change over the call rather than about a
 * moment or a total, so it reads as a closing observation rather than as
 * another statistic.
 *
 * Owns the polling itself, so it is only running while this screen is mounted.
 */
export default function FeedbackView({
  sessionId,
  followUp,
  onReverse,
}: {
  sessionId: string | null;
  /** Omitted where there is nowhere to act on the follow-up (F-60). */
  followUp?: FollowUpActions;
  /** Create and start the reverse of this Session (F-61, ADR 0070). Like
   * `followUp.onStart` it belongs to whoever owns the screen: the post-call
   * screen begins the call itself, the history hands the pairing to the
   * training flow. Omitted where there is nowhere to go with it. */
  onReverse?: (reverse: ReverseScenario) => void;
}) {
  const { detail, state } = useSessionFeedback(sessionId);

  if (!detail?.feedback) {
    return (
      <div className="card">
        <p className="muted">{NOTICE[state]}</p>
      </div>
    );
  }
  return (
    <FeedbackReport
      detail={detail}
      followUp={followUp}
      sessionId={sessionId}
      onReverse={onReverse}
    />
  );
}

/**
 * The wrap-up itself, given data that has already been fetched.
 *
 * Split from the component above so a screen that already holds a
 * `SessionDetail` — the history's detail page, which needs the Transcript from
 * the same response — can render the report without asking for it again.
 *
 * Renders nothing when the Session carries no wrap-up. What to say instead is
 * the caller's to decide, because the honest sentence differs: on the post-call
 * screen one is still being generated, in the history none ever was.
 *
 * The follow-up and reverse offers (F-60, F-61) stay props for the same
 * reason: the request that writes each is identical from both screens, what
 * happens with the answer is not — after a call the training flow is already
 * here, from the history it has to be handed over.
 */
export function FeedbackReport({
  detail,
  followUp,
  sessionId,
  onReverse,
}: {
  detail: SessionDetail;
  followUp?: FollowUpActions | undefined;
  sessionId?: string | null | undefined;
  onReverse?: ((reverse: ReverseScenario) => void) | undefined;
}) {
  const { feedback, measurements, turns, persona, scenario } = detail;
  if (!feedback) return null;

  const improvements = feedback.points.filter((p) => p.kind === "improvement");

  // Built here rather than inline below so that "is there anything to offer?"
  // and "what is on offer?" are the same question asked once — the row must
  // not appear empty, and each half has its own reason to be absent.
  //
  // Only where the wrap-up named something to work on: those points are the
  // follow-up's whole input, and the route refuses without them (ADR 0069).
  const followUpOffer =
    followUp && improvements.length > 0 ? (
      <FollowUp
        scenario={detail.follow_up}
        personaId={detail.persona_id}
        sessionId={sessionId}
        {...followUp}
      />
    ) : null;
  // No condition on the points: a reverse copies the case that was played, so
  // it is available for any call that happened — except a reverse itself, which
  // is already the other way round (ADR 0070).
  const reverseOffer =
    onReverse && sessionId && !detail.reverse ? (
      <Reverse sessionId={sessionId} onReverse={onReverse} />
    ) : null;

  return (
    <>
      <div className="feedback-meta" aria-label="Trainingsdetails">
        <span>{scenario}</span>
        <span className="feedback-meta-separator" aria-hidden="true">
          ·
        </span>
        <span>{persona}</span>
      </div>

      <div className="card feedback-summary-card">
        <div className="feedback-summary-kicker">QUALITATIVE EINORDNUNG</div>
        <h2 className="feedback-summary-title">Zusammenfassung</h2>
        <p className="feedback-summary-text">{feedback.summary}</p>
      </div>

      <div className="feedback-details">
        <PointList
          eyebrow="STÄRKEN"
          title="Das gelang gut"
          points={feedback.points.filter((p) => p.kind === "strength")}
          turns={turns}
          tone="success"
        />

        <PointList
          eyebrow="WEITERENTWICKELN"
          title="Das können Sie verbessern"
          points={improvements}
          turns={turns}
          tone="danger"
        />
      </div>

      {/* The two things to do next, side by side: they are alternatives, and
          stacked they read as a sequence. Either can be absent — a wrap-up
          with no improvement points has no follow-up to offer, and a reverse
          cannot be reversed again — and whichever is left then takes the full
          width on its own. */}
      {(followUpOffer || reverseOffer) && (
        <div className="next-steps">
          {followUpOffer}
          {reverseOffer}
        </div>
      )}

      {feedback.phase_language && <PhaseLanguage text={feedback.phase_language} />}

      <MetricSection measurements={measurements} />
    </>
  );
}

/**
 * F-42's register block: the model's reading, the pattern it is read against,
 * and — behind the "i" — where that pattern comes from.
 *
 * The note is the finding itself rather than a description of it, because that
 * is the sentence a reader can act on. What it rests on, and what it cannot
 * tell them (ADR 0056: the phase boundaries are the model's own guess), sits in
 * `InfoDetails` like every other background text in this app.
 */
function PhaseLanguage({ text }: { text: string }) {
  return (
    <section className="feedback-phase-card">
      <div className="feedback-phase-eyebrow">GESPRÄCHSFÜHRUNG</div>
      <h2 className="feedback-phase-title">Phasengerechte Sprache</h2>

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
          durch echte Servicegespräche. Kein Messwert: die Phasengrenzen schätzt das
          Sprachmodell selbst.
        </p>
        <p className="feedback-phase-source">
          Packard, Li &amp; Berger (2024), Journal of Consumer Research 51 (3);
          Kahneman et al. (1993), Psychological Science 4 (6).
        </p>
      </InfoDetails>
    </section>
  );
}

/**
 * The call's statistics (F-53), which exist independently of the narrative:
 * they are computed while the call runs (ADR 0047/0048) and stored with the
 * Session, so a Session whose wrap-up never got generated still has them.
 *
 * Never a judgement, only a reading — ADR 0051 declined to invent the norms
 * that would be needed to say whether a figure is good, and the note under the
 * grid says so rather than leaving the user to assume a direction.
 */
export function MetricSection({ measurements }: { measurements: Measurement[] }) {
  if (measurements.length === 0) return null;

  return (
    <section className="feedback-metrics-section">
      <div className="feedback-metrics-eyebrow">ERGÄNZENDE AUSWERTUNG</div>
      <h2 className="feedback-metrics-title">Kennzahlen zum Gespräch</h2>

      <div className="metric-grid">
        {measurements.map((measurement) => (
          <Metric key={measurement.key} measurement={measurement} />
        ))}
      </div>

      <p className="metric-disclaimer">
        Reine Messwerte, ohne Zielbereich: für diese Nutzergruppe gibt es keinen
        belegten Normwert, an dem sie zu messen wären.
      </p>
    </section>
  );
}

/** The next exercise, built from the points above (F-60).
 *
 * Asked for, not written unbidden (ADR 0069's amendment): the User presses the
 * button, exactly as they do for the reverse below. Until then this is an
 * offer; afterwards it is a Scenario of theirs like any other, and the same
 * card renders both — what the create route answers and what a later reload
 * brings are one shape.
 *
 * "Starten" goes straight into the call, against the Persona this training was
 * played with: the exercise follows from that conversation, so re-picking a
 * partner would be a step with only one sensible answer. The Scenario stays an
 * ordinary row in the library, so a different partner is a matter of starting
 * it from the setup screen instead. */
function FollowUp({
  scenario,
  personaId,
  sessionId,
  onEdit,
  onStart,
  onCreated,
}: {
  scenario: SessionDetail["follow_up"];
  personaId: string;
  sessionId: string | null | undefined;
} & FollowUpActions) {
  // What the create route just wrote, so the card appears without waiting for
  // a refetch. `scenario` wins: on a reload it is the same row, and on the
  // history's page it is the only source.
  const [created, setCreated] = useState<FollowUpCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const card = scenario ?? created;

  const handleClick = async () => {
    if (!sessionId) return;
    setBusy(true);
    setError(null);
    try {
      setCreated(await createFollowUp(sessionId));
      onCreated?.();
    } catch (e: unknown) {
      // The backend's `detail` is written for the user, so show it as it is.
      setError(
        e instanceof ApiError && e.detail
          ? e.detail
          : "Das Folgeszenario konnte nicht erstellt werden.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!card) {
    if (!sessionId) return null;
    return (
      <section className="card next-step">
        <div className="next-step-eyebrow">WEITER ÜBEN</div>
        <h2 className="next-step-title">Folgeszenario</h2>
        <p className="next-step-lead">
          Daraus lässt sich Ihr nächstes Gespräch bauen: eine neue Situation im selben
          Umfeld, die genau das verlangt, was hier gefehlt hat.
        </p>
        <button type="button" className="follow-up-button" disabled={busy} onClick={handleClick}>
          {busy ? "Folgeszenario wird gebaut …" : "Folgeszenario erstellen"}
        </button>
        {busy && (
          <p className="follow-up-note">
            Die Übung wird gerade geschrieben – das dauert einen Moment.
          </p>
        )}
        {error && <p className="follow-up-error">{error}</p>}
      </section>
    );
  }

  return (
    <section className="card next-step">
      <div className="next-step-eyebrow">WEITER ÜBEN</div>
      <h2 className="next-step-title">Folgeszenario</h2>
      <p className="next-step-lead">
        Daraus ist Ihr nächstes Gespräch entstanden: eine neue Situation im selben
        Umfeld, die genau das verlangt, was hier gefehlt hat. Es liegt unter
        „Folgeszenario“ in Ihrer Auswahl.
      </p>
      <p className="follow-up-name">{card.name}</p>
      <p className="follow-up-teaser">{card.short_description}</p>
      <div className="follow-up-actions">
        <button
          type="button"
          className="follow-up-button"
          onClick={() => onStart(card.id, personaId)}
        >
          Starten
        </button>
        <button type="button" className="follow-up-draft" onClick={() => onEdit(card.id)}>
          Bearbeiten
        </button>
      </div>
      <p className="follow-up-note">
        „Starten“ beginnt das Gespräch sofort – mit demselben Gesprächspartner wie in
        diesem Training, ohne Mikrofoncheck.
      </p>
    </section>
  );
}

/** "Rollen tauschen" (F-61, ADR 0070): the same call from the other side.
 *
 * Two presses, not one, and the same two the follow-up beside it takes:
 * *Rollen tauschen* writes the Scenario, *Gespräch starten* begins the call.
 * Preparing it takes a model call and the better part of a minute, so the
 * button that starts a conversation must not be the one that was pressed
 * before there was anything to start — and the User gets to read what came
 * back first. The Scenario is stored either way, so a press that is not
 * followed by a call is not a press wasted: it is in the library under its own
 * filter from then on. */
function Reverse({
  sessionId,
  onReverse,
}: {
  sessionId: string;
  onReverse: (reverse: ReverseScenario) => void;
}) {
  const [created, setCreated] = useState<ReverseScenario | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setBusy(true);
    setError(null);
    try {
      setCreated(await createReverse(sessionId));
    } catch (e: unknown) {
      // The backend's `detail` is written for the user, so show it as it is.
      setError(
        e instanceof ApiError && e.detail
          ? e.detail
          : "Der Rollentausch konnte nicht vorbereitet werden.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    return (
      <section className="card next-step reverse-offer">
        <div className="next-step-eyebrow">PERSPEKTIVE WECHSELN</div>
        <h2 className="next-step-title">Rollentausch</h2>
        <p className="next-step-lead">
          Ihr Rollentausch ist vorbereitet. Sie bekommen vor dem Gespräch die Unterlagen
          zu sehen, die die KI eben hatte.
        </p>
        <p className="follow-up-name">{created.name}</p>
        <p className="follow-up-teaser">{created.short_description}</p>
        <button
          type="button"
          className="follow-up-button"
          onClick={() => onReverse(created)}
        >
          Gespräch starten
        </button>
        <p className="follow-up-note">
          Sie rufen an, die KI nimmt ab — mit demselben Gesprächspartner wie in diesem
          Training.
        </p>
      </section>
    );
  }

  return (
    <section className="card next-step reverse-offer">
      <div className="next-step-eyebrow">PERSPEKTIVE WECHSELN</div>
      <h2 className="next-step-title">Rollentausch</h2>
      <p className="next-step-lead">
        Erleben Sie dasselbe Gespräch von der anderen Seite: Sie rufen an, die KI nimmt
        ab. Was die KI eben wusste, sehen währenddessen Sie.
      </p>
      <button type="button" className="follow-up-button" disabled={busy} onClick={handleClick}>
        {busy ? "Rollentausch wird vorbereitet …" : "Rollen tauschen"}
      </button>
      {busy && (
        <p className="follow-up-note">
          Ihre Unterlagen für das Gespräch werden zusammengestellt — das dauert einen
          Moment.
        </p>
      )}
      {error && <p className="follow-up-error">{error}</p>}
    </section>
  );
}

function PointList({
  eyebrow,
  title,
  points,
  turns,
  tone,
}: {
  eyebrow: string;
  title: string;
  points: FeedbackPoint[];
  turns: SessionTurn[];
  tone: "success" | "danger";
}) {
  if (points.length === 0) return null;
  return (
    <section className={`feedback-point-card ${tone}`}>
      <div className="feedback-point-header">
        <div className="feedback-point-icon" aria-hidden="true">
          {tone === "success" ? "✓" : "!"}
        </div>

        <div>
          <div className="feedback-point-eyebrow">{eyebrow}</div>
          <h2 className="feedback-point-title">{title}</h2>
        </div>
      </div>

      <div className="feedback-point-list">
        {points.map((point, i) => {
          const turn =
            point.turn_id !== null
              ? turns.find((candidate) => candidate.turn_id === point.turn_id)
              : undefined;

          return (
            <div className="feedback-point-item" key={i}>
              {turn && (
                <span className="feedback-point-time">
                  {formatOffset(turn.start_offset_ms)}
                </span>
              )}
              <p>{point.text}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ measurement }: { measurement: Measurement }) {
  // Loudness is shown as a course, not a figure: its value is a dB span (95th
  // percentile minus 5th) that reads like a level without being one and that no
  // validated norm places (ADR 0004/0051). Without the curve the tile is empty.
  const curve = measurement.detail?.curve_db as (number | null)[] | undefined;
  if (measurement.key === "loudness") {
    if (!curve?.some((value) => value !== null)) return null;
    return (
      <div className="metric metric-loudness">
        <span className="metric-name">{measurement.name} im Gesprächsverlauf</span>
        <LoudnessCourse values={curve} />
      </div>
    );
  }

  const decimals = DECIMALS[measurement.key] ?? 1;
  return (
    <div className="metric">
      <span className="metric-name">{measurement.name}</span>
      <span className="metric-value">
        {measurement.value.toFixed(decimals)}
        {measurement.unit && measurement.unit !== "Anzahl"
          ? ` ${measurement.unit}`
          : ""}
      </span>
    </div>
  );
}
