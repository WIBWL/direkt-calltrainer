import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api";
import { useFocusContext } from "../FocusContext";
import type { FeedbackState } from "../hooks/useSessionFeedback";
import type {
  Finding,
  FollowUpCard,
  Measurement,
  MetricAspect,
  SegmentMeasurement,
  SessionDetail,
} from "../protocol";
import { ROUTES, sessionMetricPath } from "../routes";
import { createFollowUp, createReverse, type ReverseScenario } from "../scenarioLibrary";
import { retryFeedback } from "../sessions";
import { cx } from "../utils/cx";
import { loudnessCourse } from "../utils/loudness";
import {
  formatMetricValue,
  METRIC_DISCLAIMER,
  METRIC_KEYS,
  metricParts,
  metricReading,
  metricSubline,
  openHint,
  type MetricPart,
} from "../utils/metrics";
import {
  metricGroups,
  wrapUpOutline,
  type OutlinePoint,
} from "../utils/reportOutline";
import { formatOffset } from "../utils/time";
import FilterSlider, { type FilterOption } from "./FilterSlider";
import InfoDetails from "./InfoDetails";
import LoudnessCourse from "./LoudnessCourse";
import SectionHeading from "./SectionHeading";
import { useTranscriptFocus } from "./TranscriptFocus";

/** What a screen can do with the follow-up Scenario (F-60), passed in by its owner. No
 * edit: the write routes refuse a follow-up (ADR 0069); deletion is in the info panel.
 * `onStart` gets the Persona too, since the follow-up keeps the training's partner.
 * `onCreated` fires once one was written, so the screen's library copy can reload. */
export interface FollowUpActions {
  onStart: (scenarioId: string, personaId: string) => void;
  onCreated?: (() => void) | undefined;
}

/**
 * User utterances needed before the follow-up and reverse offers appear: a call hung up
 * after a sentence has nothing to build from. Counts the User's own rows only. The routes
 * refuse under `MIN_USER_UTTERANCES` (`backend/api/sessions.py`, pinned by `tests/test_reverse.py`).
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
 * The post-call wrap-up (F-09/F-10/F-53): the model's narrative and the statistics it
 * was written from, the figures as evidence, never a score (ADR 0004/0049/0051). The
 * Session is polled once in `App` and handed in, so the PDF reads the same `detail`.
 */
export default function FeedbackView({
  detail,
  state,
  sessionId,
  onRetry,
  followUp,
  onReverse,
  next,
}: {
  /** The polled Session. Null while it has not arrived, and for a call that
   * was never stored. */
  detail: SessionDetail | null;
  state: FeedbackState;
  /** The Session to ask again about, where a failed wrap-up can be retried.
   *  Null on a call that was never stored — there is nothing to generate. */
  sessionId?: string | null;
  /** Poll again, once the retry has been accepted. Omitted on a screen that
   *  does not poll (the history reads once), where the retry is not offered. */
  onRetry?: () => void;
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
}) {
  if (!detail?.feedback) {
    return (
      <>
        <div className="card">
          <p className="muted">{NOTICE[state]}</p>
          {/* The one state that was a dead end. The work is still possible —
              a wrap-up is written from the stored Transcript and Measurements,
              never from audio (ADR 0048/0049) — and until now the only way to
              ask for it again ran inside the container. */}
          {state === "failed" && sessionId && onRetry && (
            <RetryFeedback sessionId={sessionId} onQueued={onRetry} />
          )}
        </div>
        {next}
      </>
    );
  }
  return (
    <FeedbackReport detail={detail} followUp={followUp} onReverse={onReverse} next={next} />
  );
}

/**
 * The wrap-up itself, given fetched data, without the post-call notices, so the history's
 * page can render it too. Renders nothing without a wrap-up: what to say instead differs
 * per screen. The follow-up/reverse offers (F-60, F-61) are props for the same reason.
 */
export function FeedbackReport({
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

/**
 * The call's statistics (F-53), computed during the call (ADR 0047/0048), so a Session
 * with no wrap-up still has them. A reading, never a judgement (ADR 0051), and the note
 * under the grid says so.
 */
export function MetricSection({
  measurements,
  findings = [],
  notes = {},
  sessionId = null,
  segments = [],
}: {
  measurements: Measurement[];
  /** Individual moments noted during the call, e.g. F-51's interruptions.
   *  Used here only to decide which tiles have a page worth opening. */
  findings?: Finding[];
  /** The long explanation behind a metric's "i", by metric key. */
  notes?: Record<string, string>;
  /** The Session these figures belong to, for the per-metric page. Null on a
   *  call that was never stored, where there is nothing to link to. */
  sessionId?: string | null;
  /** The same metrics over the demanding stretches and over the rest
   *  (ADR 0081). Used here only to say that the comparison exists: it is two
   *  figures per metric, which is a table and belongs on the metric's own
   *  page. */
  segments?: SegmentMeasurement[];
}) {
  // Opens on the paraverbal half: the one reading the transcript cannot give.
  const [aspect, setAspect] = useState<MetricAspect>("how");

  const groups = metricGroups(measurements);
  const all = groups.flatMap((group) => group.measurements);

  const options: FilterOption<MetricAspect>[] = groups.map((group) => ({
    value: group.aspect,
    label: group.label,
    count: group.measurements.length,
  }));
  // Nothing to switch between when one half is empty: show what there is.
  const split = options.every((option) => option.count > 0);
  const current = groups.find((group) => group.aspect === aspect)!;
  const shown = split ? current.measurements : all;

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
          <p className="feedback-metrics-lead">{current.lead}</p>
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

      {/* Names the exception to the sentence above: two metrics carry a word beside their
          figure. Kept out of `METRIC_DISCLAIMER` because the PDF prints figures without
          readings. */}
      <p className="metric-disclaimer">
        {METRIC_DISCLAIMER} Wo „Einschätzung“ steht, haben wir die Schwellen selbst
        gesetzt; welche das sind, steht jeweils dabei.
      </p>

      <MetricNotes measured={all} segments={segments} />

      {/* Last, pointing to the same figure across trainings, which this screen cannot
          answer. Only for a stored Session: without consent there is nothing to compare
          (ADR 0066). */}
      {sessionId && (
        <p className="metric-progress-link">
          <Link to={ROUTES.progress}>
            Diese Zahlen über Ihre Trainings hinweg ansehen
          </Link>
        </p>
      )}
    </section>
  );
}

/**
 * What the grid cannot say: that a metric could not be measured and so left no tile
 * (ADR 0085; which one is not named, the frontend would have to guess why), and that a
 * second reading exists where the wrap-up marked demanding stretches (ADR 0081).
 */
function MetricNotes({
  measured,
  segments,
}: {
  measured: Measurement[];
  segments: SegmentMeasurement[];
}) {
  const shown = new Set(measured.map((m) => m.key));
  // Counted off the catalogue the frontend already keeps, so a metric added on
  // the backend does not have to be listed here a second time.
  const missing = METRIC_KEYS.filter((key) => !shown.has(key)).length;
  // Distinct metrics, not rows: each one that was compared carries two, one
  // per stretch. The wire never sends the whole call here -- that is what
  // `measurements` is -- so nothing has to be filtered out first.
  const compared = new Set(segments.map((entry) => entry.key)).size;

  if (missing === 0 && compared === 0) return null;

  return (
    <div className="metric-footnotes">
      {compared > 0 && (
        <p>
          Für {compared} dieser Kennzahlen wurde zusätzlich verglichen, wie Sie an den
          fordernden Stellen dieses Gesprächs gesprochen haben und wie im Rest. Der Vergleich
          steht auf der Seite der jeweiligen Kennzahl.
        </p>
      )}
      {missing > 0 && (
        <p>
          Nicht jede Kennzahl ließ sich in diesem Gespräch messen.{" "}
          <InfoDetails label="Woran das liegen kann">
            <p>
              Manche Kennzahlen brauchen eine Mindestlänge: Bei einem Gespräch von wenigen
              Sätzen gibt es zum Beispiel keinen Abschluss, der sich von der Begrüßung
              trennen ließe.
            </p>
            <p>
              Andere brauchen eine Aufnahme, in der sich Stille von Sprache trennen lässt.
              Läuft im Hintergrund ein Geräusch mit, findet das Verfahren keine Pausen mehr.
              Dann werden die betroffenen Kennzahlen weggelassen statt falsch angezeigt.
            </p>
            <p>
              In beiden Fällen sagt das etwas über die Aufnahme und nichts über Ihr Gespräch.
            </p>
          </InfoDetails>
        </p>
      )}
    </div>
  );
}

/** The one metric whose unit a reader cannot place. Matches
 *  `intonation.RANGE_KEY` on the backend. */
const INTONATION_KEY = "intonation";

/**
 * One press that writes a Scenario out of this Session — follow-up or reverse (ADR 0069,
 * ADR 0070). The backend's `detail` is shown as is, `fallback` where there is none. `run`
 * resolves to what was written, or null on failure.
 */
function useCreate<T>(create: () => Promise<T>, fallback: string) {
  const [created, setCreated] = useState<T | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (): Promise<T | null> => {
    setBusy(true);
    setError(null);
    try {
      const result = await create();
      setCreated(result);
      return result;
    } catch (e: unknown) {
      setError(e instanceof ApiError && e.detail ? e.detail : fallback);
      return null;
    } finally {
      setBusy(false);
    }
  };

  return { created, busy, error, run };
}

/** The frame both offers share, before and after their Scenario is written:
 *  eyebrow, title, one lead paragraph, and whatever the offer is right now. */
function NextStepCard({
  eyebrow,
  title,
  lead,
  className,
  children,
}: {
  eyebrow: string;
  title: string;
  lead: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx("card next-step", className)}>
      <div className="next-step-eyebrow">{eyebrow}</div>
      <h2 className="next-step-title">{title}</h2>
      <p className="next-step-lead">{lead}</p>
      {children}
    </section>
  );
}

/** The first press: the button that writes the Scenario, and what to say while
 *  that runs or after it failed. */
function CreateButton({
  label,
  busyLabel,
  busyNote,
  busy,
  error,
  onClick,
}: {
  label: string;
  busyLabel: string;
  busyNote: string;
  busy: boolean;
  error: string | null;
  onClick: () => void;
}) {
  return (
    <>
      <button type="button" className="follow-up-button" disabled={busy} onClick={onClick}>
        {busy ? busyLabel : label}
      </button>
      {busy && <p className="follow-up-note">{busyNote}</p>}
      {error && <p className="follow-up-error">{error}</p>}
    </>
  );
}

/** The second press: the written Scenario, named, and the button that starts
 *  it. The button sits in its own row wrapper — that is where the space above
 *  it comes from, so both offers are spaced alike without the number being
 *  written twice. */
function StartCreated({
  name,
  teaser,
  note,
  onStart,
}: {
  name: string;
  teaser: string;
  note: string;
  onStart: () => void;
}) {
  return (
    <>
      <p className="follow-up-name">{name}</p>
      <p className="follow-up-teaser">{teaser}</p>
      <div className="follow-up-actions">
        <button type="button" className="follow-up-button" onClick={onStart}>
          Starten
        </button>
      </div>
      <p className="follow-up-note">{note}</p>
    </>
  );
}

/** The next call in the same matter, built from the points above (F-60). Asked for by
 * the User (ADR 0069's amendment); the same card renders the offer and the written row.
 * Starting skips the mic check and uses this training's Persona; another partner means
 * starting it from the setup screen. */
function FollowUp({
  scenario,
  personaId,
  sessionId,
  onStart,
  onCreated,
}: {
  scenario: FollowUpCard | null;
  personaId: string;
  sessionId: string;
} & FollowUpActions) {
  const create = useCreate(
    () => createFollowUp(sessionId),
    "Das Folgeszenario konnte nicht erstellt werden.",
  );
  // What the create route just wrote, so the card appears without waiting for
  // a refetch. `scenario` wins: on a reload it is the same row, and on the
  // history's page it is the only source.
  const card = scenario ?? create.created;

  if (!card) {
    return (
      <NextStepCard
        eyebrow="WEITER ÜBEN"
        title="Folgeszenario"
        lead="Daraus lässt sich Ihr nächstes Gespräch bauen: derselbe Fall, einige Zeit später – diesmal so, dass genau das nötig ist, was hier gefehlt hat."
      >
        <CreateButton
          label="Folgeszenario erstellen"
          busyLabel="Folgeszenario wird gebaut …"
          busyNote="Die Übung wird gerade geschrieben – das dauert einen Moment."
          busy={create.busy}
          error={create.error}
          onClick={() =>
            void create.run().then((written) => {
              if (written) onCreated?.();
            })
          }
        />
      </NextStepCard>
    );
  }

  return (
    <NextStepCard
      eyebrow="WEITER ÜBEN"
      title="Folgeszenario"
      lead="Daraus ist Ihr nächstes Gespräch entstanden: derselbe Fall, einige Zeit später – diesmal so, dass genau das nötig ist, was hier gefehlt hat. Es liegt unter „Folgeszenario“ in Ihrer Auswahl."
    >
      <StartCreated
        name={card.name}
        teaser={card.short_description}
        onStart={() => onStart(card.id, personaId)}
        note="„Starten“ ruft denselben Gesprächspartner wie in diesem Training an – ohne Mikrofoncheck. Das Gespräch beginnt, sobald Sie den Anruf annehmen."
      />
    </NextStepCard>
  );
}

/** The Reverse offer (F-61, ADR 0070): the same call from the other side. Two presses,
 * like the follow-up: the first writes the Scenario (a model call, most of a minute), the
 * second begins the call, so the start button is never the one pressed before there was
 * anything to start. The Scenario is stored either way. */
function Reverse({
  sessionId,
  onReverse,
}: {
  sessionId: string;
  onReverse: (reverse: ReverseScenario) => void;
}) {
  const create = useCreate(
    () => createReverse(sessionId),
    "Der Rollentausch konnte nicht vorbereitet werden.",
  );
  const created = create.created;

  if (created) {
    return (
      <NextStepCard
        eyebrow="PERSPEKTIVE WECHSELN"
        title="Rollentausch"
        className="reverse-offer"
        lead="Ihr Rollentausch ist vorbereitet. Sie bekommen vor dem Gespräch die Unterlagen zu sehen, die die KI eben hatte."
      >
        <StartCreated
          name={created.name}
          teaser={created.short_description}
          onStart={() => onReverse(created)}
          note="Sie rufen an, die KI nimmt ab — mit demselben Gesprächspartner wie in diesem Training."
        />
      </NextStepCard>
    );
  }

  return (
    <NextStepCard
      eyebrow="PERSPEKTIVE WECHSELN"
      title="Rollentausch"
      className="reverse-offer"
      lead="Erleben Sie dasselbe Gespräch von der anderen Seite: Sie rufen an, die KI nimmt ab. Was die KI eben wusste, sehen währenddessen Sie."
    >
      <CreateButton
        label="Rollen tauschen"
        busyLabel="Rollentausch wird vorbereitet …"
        busyNote="Ihre Unterlagen für das Gespräch werden zusammengestellt — das dauert einen Moment."
        busy={create.busy}
        error={create.error}
        onClick={() => void create.run()}
      />
    </NextStepCard>
  );
}

/**
 * Ask for the wrap-up once more. On a refusal it shows the server's sentence, since the
 * reasons (a job still running, nothing to summarise) are invisible here. On success
 * polling resumes at once.
 */
function RetryFeedback({
  sessionId,
  onQueued,
}: {
  sessionId: string;
  onQueued: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    setBusy(true);
    setError(null);
    try {
      await retryFeedback(sessionId);
      onQueued();
    } catch (e) {
      setError(
        e instanceof ApiError && e.detail
          ? e.detail
          : "Die Auswertung konnte nicht angefordert werden. Bitte später noch einmal versuchen.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="follow-up-button"
        disabled={busy}
        onClick={() => void ask()}
      >
        {busy ? "Wird angefordert …" : "Auswertung erneut erstellen"}
      </button>
      {error && <p className="follow-up-error">{error}</p>}
    </>
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

function Metric({
  measurement,
  sessionId,
  detailed,
}: {
  measurement: Measurement;
  /** Null on a call that was never stored, where there is no page to open. */
  sessionId: string | null;
  /** Whether this metric has a page worth opening. */
  detailed: boolean;
}) {
  // Loudness is shown as a course, not a figure: its dB span reads like a level without
  // being one (ADR 0004/0051). The course arrives in the Measurement's detail (ADR 0091),
  // so the wrap-up's sentence about it cannot disagree with the picture.
  const curve = measurement.key === "loudness" ? loudnessCourse(measurement.detail) : null;
  if (measurement.key === "loudness" && !curve) return null;

  const context = interruptionContext(measurement);
  const detail = metricSubline(measurement);
  // The step this call landed on, in words, and its colour (`metricReading`; F-51's
  // traffic light and F-35's reading). The light colours the figure only, never the
  // whole tile: its thresholds are unvalidated working values (`interruptions.py`).
  // For F-35 the tile leads with the classification word, so the colour sits on that;
  // it must never sit on the semitone figure, a different measurement from the step's.
  const { label: reading, readingLight } = metricReading(measurement);

  const figure = formatMetricValue(measurement);

  // Intonation's unit is one a reader cannot place, so the reading leads and the
  // semitone range stands under it (ADR 0077). Never dropped: without it only the part
  // resting on thresholds would be left (ADR 0004/0051, ADR 0088).
  const melody = measurement.key === INTONATION_KEY;
  const parts = metricParts(measurement);

  const body = curve ? (
    <>
      <span className="metric-name">{measurement.name} im Gesprächsverlauf</span>
      <LoudnessCourse curve={curve} />
    </>
  ) : (
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

  // One class list for both, so the loudness tile keeps its own width whether
  // or not it opens. It used to return early and could therefore never be a
  // link, which left the one tile carrying a drawing as the one tile with no
  // way to see it larger.
  const className = `metric${curve ? " metric-loudness" : ""}`;

  if (!detailed || !sessionId) {
    return <div className={className}>{body}</div>;
  }

  return (
    <Link
      className={`${className} metric-open`}
      to={sessionMetricPath(sessionId, measurement.key)}
    >
      {body}
      <span className="metric-open-hint">{openHint(measurement.key)}</span>
    </Link>
  );
}

/**
 * The count set against the call it happened in: context beside the figure, never a
 * rate (a rate put one interruption in a short call on the top step). Backchannels are
 * named as not counting, so an attentive call and an absent one read differently.
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

/** A checklist metric's headline — the opening's (F-63) or the closing's
 *  (ADR 0089): its parts, each marked, in place of a count that reads like a
 *  grade. The screen reader hears "not recognised", never "missing": a bare
 *  name or a recap worded some other way slips past the patterns. */
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
