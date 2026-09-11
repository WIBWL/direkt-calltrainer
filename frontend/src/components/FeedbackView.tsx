import { useEffect, useState, type ReactNode } from "react";

import { ApiError } from "../api";
import type {
  FeedbackPoint,
  Finding,
  Measurement,
  MetricAspect,
  SessionDetail,
  SessionTurn,
  TrafficLight,
} from "../protocol";
import { Link } from "react-router-dom";

import { sessionMetricPath } from "../routes";
import {
  ASPECT_LABELS,
  ASPECT_LEADS,
  formatMetricValue,
  loudnessCurve,
  METRIC_ASPECTS,
  METRIC_DISCLAIMER,
  metricAspect,
  metricParts,
  metricSubline,
  withDerived,
  type MetricPart,
} from "../utils/metrics";
import { formatOffset } from "../utils/time";
import { useSessionFeedback } from "../hooks/useSessionFeedback";
import {
  createFollowUp,
  createReverse,
  type FollowUpCard,
  type ReverseScenario,
} from "../scenarioLibrary";
import FilterSlider, { type FilterOption } from "./FilterSlider";
import InfoDetails from "./InfoDetails";
import LoudnessCourse from "./LoudnessCourse";
import SectionHeading from "./SectionHeading";

/** What a screen can do with the follow-up Scenario (F-60): open it in the
 * start it as the next call. That belongs to whoever owns the screen, so it is
 * passed in — the post-call screen starts the call itself, the history hands
 * the pairing to the training flow.
 *
 * There is no edit beside it: a follow-up is the exercise one reading of the
 * wrap-up produced (ADR 0069), and the write routes refuse it the way they
 * refuse a reverse. Removing it is the one thing left to do with one, and that
 * is offered where a reverse's is — in the info panel behind its card.
 *
 * `onStart` gets the Persona too: the follow-up is played against the same
 * partner as the training it came out of, so there is nothing left to choose.
 *
 * `onCreated` fires once the User has asked for one and it has been written
 * (ADR 0069's amendment). The card renders from the answer either way; this is
 * for the screen's own copy of the library, which does not hold the new row
 * yet and is what "Starten" reads its names off. */
export interface FollowUpActions {
  onStart: (scenarioId: string, personaId: string) => void;
  onCreated?: (() => void) | undefined;
}

/**
 * How many times the User has to have spoken before the two offers under
 * "Nächste Schritte" appear at all.
 *
 * Both build a new exercise out of *this* call: the follow-up carries the case
 * forward from where it ended (ADR 0069), the reverse replays it from the other
 * side (ADR 0070). A call that was hung up after a sentence or two has no
 * "where it ended" to carry anywhere — it would cost a model call and the
 * better part of a minute to produce an exercise drafted from nothing. So they
 * are not offered there rather than offered and disappointing.
 *
 * Counted in the User's own utterances: `turns` is the stored transcript, one
 * row per speaker (ADR 0051), so the Persona's greeting and its answer to a
 * single "Hallo?" would otherwise make three on their own.
 */
const MIN_USER_TURNS = 3;

/** Everything that is not a finished wrap-up is a one-line notice. There is
 * no entry for "ready": the hook reports it only once feedback is present. */
const NOTICE: Record<string, string> = {
  loading: "Das Feedback wird erstellt. Einen Moment bitte.",
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
  next,
  onDetail,
}: {
  sessionId: string | null;
  /** Omitted where there is nowhere to act on the follow-up (F-60). */
  followUp?: FollowUpActions;
  /** Create and start the reverse of this Session (F-61, ADR 0070). Like
   * `followUp.onStart` it belongs to whoever owns the screen: the post-call
   * screen begins the call itself, the history hands the pairing to the
   * training flow. Omitted where there is nowhere to go with it. */
  onReverse?: (reverse: ReverseScenario) => void;
  /** What to play next (F-64). Shown without a wrap-up too: it needs no
   *  stored Session, so a call that was not kept still gets it. */
  next?: ReactNode;
  /** Hands the Session on once it has been polled, for a screen that needs the
   * same wrap-up for something other than rendering it — the post-call screen
   * puts it in the downloadable report (F-64). Not a second request: this
   * component is the only one polling, and the file must say exactly what the
   * page above it says. */
  onDetail?: (detail: SessionDetail | null) => void;
}) {
  const { detail, state } = useSessionFeedback(sessionId);

  // In an effect rather than during the render: the owner stores it, and a
  // parent state update from inside a child's render body is a loop.
  useEffect(() => onDetail?.(detail), [detail, onDetail]);

  if (!detail?.feedback) {
    return (
      <>
        <div className="card">
          <p className="muted">{NOTICE[state]}</p>
        </div>
        {next}
      </>
    );
  }
  return (
    <FeedbackReport
      detail={detail}
      followUp={followUp}
      sessionId={sessionId}
      onReverse={onReverse}
      next={next}
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
  next,
}: {
  detail: SessionDetail;
  followUp?: FollowUpActions | undefined;
  sessionId?: string | null | undefined;
  onReverse?: ((reverse: ReverseScenario) => void) | undefined;
  next?: ReactNode;
}) {
  const { feedback, measurements, turns } = detail;
  if (!feedback) return null;

  const improvements = feedback.points.filter((p) => p.kind === "improvement");
  const spokenTurns = turns.filter((turn) => turn.speaker === "user").length;
  const longEnough = spokenTurns >= MIN_USER_TURNS;

  // Built here rather than inline below so that "is there anything to offer?"
  // and "what is on offer?" are the same question asked once — the row must
  // not appear empty, and each half has its own reason to be absent.
  //
  // Only where the wrap-up named something to work on: those points are the
  // follow-up's whole input, and the route refuses without them (ADR 0069).
  const followUpOffer =
    followUp && longEnough && improvements.length > 0 ? (
      <FollowUp
        scenario={detail.follow_up}
        personaId={detail.persona_id}
        sessionId={sessionId}
        {...followUp}
      />
    ) : null;
  // No condition on the points: a reverse copies the case that was played, so
  // it is available for any call that was actually conducted — except a reverse
  // itself, which is already the other way round (ADR 0070).
  const reverseOffer =
    onReverse && longEnough && sessionId && !detail.reverse ? (
      <Reverse sessionId={sessionId} onReverse={onReverse} />
    ) : null;

  // No meta row here any more: which case, which partner and which side the
  // User was on describe the *call*, not the wrap-up, and a Session whose
  // wrap-up never got written still has all three. `FeedbackScreen` shows them
  // under the title of both screens instead.
  return (
    <>
      <section className="feedback-section">
        <SectionHeading eyebrow="QUALITATIVE EINORDNUNG" title="Zusammenfassung" />
        <div className="feedback-box">
          <p className="feedback-summary-text">{feedback.summary}</p>
        </div>
      </section>

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

      {feedback.phase_language && <PhaseLanguage text={feedback.phase_language} />}

      <MetricSection
        measurements={measurements}
        findings={detail.findings}
        notes={detail.metric_notes}
        sessionId={detail.session_id}
      />

      {/* Last, because it is what to do *after* reading all of the above. The
          two are side by side: they are alternatives, and stacked they read as
          a sequence. Either can be absent — a wrap-up with no improvement
          points has no follow-up to offer, a reverse cannot be reversed
          again, and a call too short to build anything out of offers neither —
          and whichever is left then takes the full width on its own.

          The next-call offers (F-64) sit under that row, inside the same
          section: they are one more thing to pick, which is what an item under
          "Nächste Schritte" is. Where neither offer above exists they stand on
          their own instead. `next` is an element even when it renders nothing,
          so it cannot decide whether the heading appears, and a heading over an
          empty section is worse than no heading. */}
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

/**
 * The call's statistics (F-53), which exist independently of the narrative:
 * they are computed while the call runs (ADR 0047/0048) and stored with the
 * Session, so a Session whose wrap-up never got generated still has them.
 *
 * Never a judgement, only a reading — ADR 0051 declined to invent the norms
 * that would be needed to say whether a figure is good, and the note under the
 * grid says so rather than leaving the user to assume a direction.
 */
export function MetricSection({
  measurements,
  findings = [],
  notes = {},
  sessionId = null,
}: {
  measurements: Measurement[];
  /** Individual moments noted during the call, e.g. F-51's interruptions.
   *  Used here only to decide which tiles have a page worth opening. */
  findings?: Finding[];
  /** The long explanation behind a Kennzahl's "i", by metric key. */
  notes?: Record<string, string>;
  /** The Session these figures belong to, for the per-Kennzahl page. Null on a
   *  call that was never stored, where there is nothing to link to. */
  sessionId?: string | null;
}) {
  // Opens on the paraverbal half: the one reading the transcript cannot give.
  const [aspect, setAspect] = useState<MetricAspect>("how");

  const all = withDerived(measurements);

  const options: FilterOption<MetricAspect>[] = METRIC_ASPECTS.map((value) => ({
    value,
    label: ASPECT_LABELS[value],
    count: all.filter((m) => metricAspect(m) === value).length,
  }));
  // Nothing to switch between when one half is empty: show what there is.
  const split = options.every((option) => option.count > 0);
  const shown = split ? all.filter((m) => metricAspect(m) === aspect) : all;

  if (all.length === 0) return null;

  const detailed = new Set([
    ...findings.map((f) => f.metric_key).filter((key): key is string => key !== null),
    ...Object.keys(notes),
  ]);

  return (
    <section className="feedback-section feedback-metrics-section">
      <SectionHeading eyebrow="ERGÄNZENDE AUSWERTUNG" title="Kennzahlen zum Gespräch" />

      {split && (
        <div className="feedback-metrics-filter">
          <FilterSlider
            options={options}
            value={aspect}
            onChange={setAspect}
            label="Kennzahlen nach Art filtern"
          />
          <p className="feedback-metrics-lead">{ASPECT_LEADS[aspect]}</p>
        </div>
      )}

      <div className="metric-grid">
        {shown.map((measurement) => (
          <Metric
            key={measurement.key}
            measurement={measurement}
            sessionId={sessionId}
            detailed={detailed.has(measurement.key)}
          />
        ))}
      </div>

      {/* The second sentence exists because the first one is contradicted a
          few pixels above it: two Kennzahlen now carry a word beside their
          figure. Rather than quietly dropping the claim, the exception is
          named and bounded — it is what the reader is looking at. It stays out
          of the shared `METRIC_DISCLAIMER` because the PDF prints the figures
          without their readings, and there the sentence would point at
          nothing. */}
      <p className="metric-disclaimer">
        {METRIC_DISCLAIMER} Wo „Einschätzung“ steht, haben wir die Schwellen selbst
        gesetzt; welche das sind, steht jeweils dabei.
      </p>
    </section>
  );
}

/** The one Kennzahl whose unit a reader cannot place. Matches
 *  `intonation.RANGE_KEY` on the backend. */
const INTONATION_KEY = "intonation";

/** The next call in the same matter, built from the points above (F-60).
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
          Daraus lässt sich Ihr nächstes Gespräch bauen: derselbe Fall, einige Zeit
          später – diesmal so, dass genau das nötig ist, was hier gefehlt hat.
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
        Daraus ist Ihr nächstes Gespräch entstanden: derselbe Fall, einige Zeit
        später – diesmal so, dass genau das nötig ist, was hier gefehlt hat. Es liegt
        unter „Folgeszenario“ in Ihrer Auswahl.
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
      </div>
      <p className="follow-up-note">
        „Starten“ ruft denselben Gesprächspartner wie in diesem Training an – ohne
        Mikrofoncheck. Das Gespräch beginnt, sobald Sie den Anruf annehmen.
      </p>
    </section>
  );
}

/** "Rollen tauschen" (F-61, ADR 0070): the same call from the other side.
 *
 * Two presses, not one, and the same two the follow-up beside it takes:
 * *Rollen tauschen* writes the Scenario, *Starten* begins the call — the same
 * word the follow-up beside it uses, because it is the same second press.
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
        {/* In the same row wrapper the follow-up's button sits in, rather
            than bare under the teaser: that is where the 0.9rem above it comes
            from, and sharing the wrapper is what keeps the two offers spaced
            alike without the number being written twice. */}
        <div className="follow-up-actions">
          <button
            type="button"
            className="follow-up-button"
            onClick={() => onReverse(created)}
          >
            Starten
          </button>
        </div>
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
    <section className="feedback-section">
      <SectionHeading
        eyebrow={eyebrow}
        title={title}
        tone={tone}
        icon={tone === "success" ? "✓" : "!"}
      />

      <div className={`feedback-box feedback-point-list ${tone}`}>
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

function Metric({
  measurement,
  sessionId,
  detailed,
}: {
  measurement: Measurement;
  /** Null on a call that was never stored, where there is no page to open. */
  sessionId: string | null;
  /** Whether this Kennzahl has a page worth opening. */
  detailed: boolean;
}) {
  // Loudness is shown as a course, not a figure: its value is a dB span (95th
  // percentile minus 5th) that reads like a level without being one and that no
  // validated norm places (ADR 0004/0051). Without the curve the tile is empty.
  if (measurement.key === "loudness") {
    const curve = loudnessCurve(measurement);
    if (!curve) return null;
    return (
      <div className="metric metric-loudness">
        <span className="metric-name">{measurement.name} im Gesprächsverlauf</span>
        <LoudnessCourse values={curve} />
      </div>
    );
  }

  const light = measurement.detail?.light as TrafficLight | undefined;
  const context = interruptionContext(measurement);
  const detail = metricSubline(measurement);
  // The step this call landed on, in words. Two Kennzahlen carry one: F-51's
  // traffic light and F-35's three-step reading. F-35's is read off the pitch
  // variation quotient in the detail and not off the Umfang this tile shows,
  // that being the figure with a published boundary behind it. Both come from
  // the backend, beside the thresholds they were read off.
  const reading = (measurement.detail?.light_label ??
    measurement.detail?.liveliness_label) as string | undefined;

  // The traffic light colours the figure and nothing else. It is the only
  // colour in this application that says something about a value, the two
  // thresholds behind it are working values that nothing has validated (see
  // `interruptions.py`), and a whole tile in that colour would shout an
  // orientation. The step is written out underneath, so colour is never the
  // only channel, and the scale it comes from is on the page behind the tile.
  //
  // F-35 carries a light too now (ADR 0077, `intonation.LIGHTS`), and it lands
  // in the right place without a special case: this tile leads with the *word*
  // for Sprachmelodie, so the colour sits on the classification, which is what
  // it was read from. It must never sit on the semitone figure, which is a
  // different measurement from the one the step came out of.
  const readingLight = (measurement.detail?.liveliness_light ?? light) as
    | TrafficLight
    | undefined;

  const figure = formatMetricValue(measurement);

  // Sprachmelodie is the one Kennzahl whose unit a reader cannot place, so the
  // reading leads and the semitones stand under it. Since ADR 0077 the reading
  // comes from the pitch variation quotient and the figure is the Umfang, so the
  // figure is the measurement shown beside the reading rather than its evidence.
  // It is never dropped: without it only the part resting on thresholds would be
  // left, which is the wrong half to keep (ADR 0004/0051, ADR 0088). Every other
  // tile leads with its measurement and lets the reading follow.
  const melody = measurement.key === INTONATION_KEY;
  const parts = metricParts(measurement);

  const body = (
    <>
      <span className="metric-name">{measurement.name}</span>
      {parts ? (
        <MetricParts parts={parts} />
      ) : (
        <span className={`metric-value${readingLight ? ` metric-value-${readingLight}` : ""}`}>
          {melody && reading ? reading : figure}
        </span>
      )}

      {melody ? (
        <span className="metric-subline">
          {reading ? `Einschätzung · ${figure}` : "Zu wenig Stimme für eine Einordnung"}
        </span>
      ) : (
        detail && <span className="metric-subline">{detail}</span>
      )}

      {context && <span className="metric-context">{context}</span>}

      {reading && !melody && (
        <span className="metric-light-label">
          <span className={readingLight ? `metric-value-${readingLight}` : undefined}>
            {reading}
          </span>{" "}
          <span className="metric-light-caveat">(Einschätzung)</span>
        </span>
      )}
    </>
  );

  if (!detailed || !sessionId) {
    return <div className="metric">{body}</div>;
  }

  return (
    <Link className="metric metric-open" to={sessionMetricPath(sessionId, measurement.key)}>
      {body}
      <span className="metric-open-hint">{OPEN_HINT[measurement.key] ?? "Ansehen"}</span>
    </Link>
  );
}

/** What the tile promises behind it, per Kennzahl. The interruptions page shows
 *  transcript excerpts, the intonation page the contour and what it says —
 *  "Einzelne Stellen" would be wrong for the second, and the second only offers
 *  a page at all when the block below could not be drawn. */
const OPEN_HINT: Record<string, string> = {
  interruptions: "Einzelne Stellen ansehen",
  intonation: "Diese Kennzahl ansehen",
};

/**
 * The count set against the call it happened in.
 *
 * Context beside the figure, never inside it: dividing by the call length or by
 * the number of Persona replies was tried and put a single interruption on the
 * top step of a short call. The traffic light stays on the count; this line is
 * what lets a reader weigh that count for themselves.
 *
 * The backchannels are named here too, and named as not counting. Listening is
 * the other half of this goal, and a figure that only ever counted the failures
 * would describe an attentive call and an absent one identically.
 */
function interruptionContext(measurement: Measurement): string | null {
  if (measurement.key !== "interruptions") return null;
  const detail = measurement.detail ?? {};
  const callMs = (detail.call_ms as number | undefined) ?? 0;
  const turns = detail.persona_turns as number | undefined;
  const backchannels = (detail.backchannel_count as number | undefined) ?? 0;

  const parts: string[] = [];
  if (callMs > 0) parts.push(`in ${Math.max(1, Math.round(callMs / 60000))} Gesprächsminuten`);
  if (turns) parts.push(`bei ${turns} Redebeiträgen des Gegenübers`);
  if (backchannels > 0) {
    parts.push(
      `${backchannels} bestätigende${backchannels === 1 ? "s Hörsignal" : " Hörsignale"} zählen nicht mit`,
    );
  }
  return parts.length > 0 ? parts.join(", ") : null;
}

/** A checklist Kennzahl's headline — the opening's (F-63) or the closing's
 *  (ADR 0089): its parts, each marked, in place of a count that reads like a
 *  grade. "nicht erkannt" for the screen reader, never "fehlt": a bare name or
 *  a recap worded some other way slips past the patterns. */
function MetricParts({ parts }: { parts: MetricPart[] }) {
  return (
    <span className="metric-parts">
      {parts.map(({ key, label, said }) => (
        <span key={key} className={"metric-part" + (said ? " is-said" : "")}>
          <span aria-hidden="true">{said ? "✓" : "–"}</span> {label}
          <span className="visually-hidden">{said ? " erkannt" : " nicht erkannt"}</span>
        </span>
      ))}
    </span>
  );
}

