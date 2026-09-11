import { useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { useFocusContext } from "../FocusContext";
import { useProgressData } from "../hooks/useProgressData";
import type { FocusGoal, MetricAspect, SessionSummary } from "../protocol";
import { ROUTES, progressGoalPath, progressMetricPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import { mentionsFor } from "../utils/goalMentions";
import { GROUPS, groupOf } from "../utils/metricGroups";
import { segmentTrainings } from "../utils/segmentStats";
import {
  MIN_SESSIONS_FOR_SERIES,
  activity,
  durationSeries,
  formatValue,
  variety,
  withinPeriod,
  toSeries,
  type MetricSeries,
} from "../utils/progressStats";
import { formatDate } from "../utils/time";
import ActivityCalendar from "./ActivityCalendar";
import AppLayout from "./AppLayout";
import FilterSlider from "./FilterSlider";
import ProgressPractice from "./ProgressPractice";
import ProgressRecurring from "./ProgressRecurring";
import Sparkline from "./Sparkline";
import VarietyGrid from "./VarietyGrid";

/** The periods the user can switch between. Six months is the retention limit
 *  (ADR 0067), so "Gesamt" means everything still stored and nothing older. */
const PERIODS = [
  { key: "30", label: "30 Tage", days: 30 },
  { key: "180", label: "6 Monate", days: 180 },
  { key: "all", label: "Gesamt", days: null },
] as const;

type PeriodKey = (typeof PERIODS)[number]["key"];

/**
 * The progress dashboard (F-13, docs/dashboard-konzept.md).
 *
 * Three questions in the order Hattie & Timperley put them: where am I going
 * (the focus goals), how am I going (the Kennzahlen over time), what next
 * (what the wrap-ups keep coming back to, and the one thing to practise next).
 * Both used to be a labelled placeholder; they became real once each feedback
 * point carried the focus goal it was about (ADR 0080) --
 * `ProgressRecurring` counts what recurs, `ProgressPractice` turns the most
 * frequent improvement into a single suggestion with a button.
 *
 * Everything numeric on this screen was measured when a call ended and stored
 * with the Session (ADR 0051); this view groups those values and describes
 * their spread. It evaluates none of them: no target band, no colour meaning
 * good, no arrow, no aggregate score. ADR 0065 rules those out for this screen
 * specifically, and the reason is that nobody has established what a good
 * Redeanteil or a good Sprechtempo is for this population. What the user gets
 * instead is their own behaviour made visible, with the interpretation left to
 * them and to the qualitative wrap-ups.
 *
 * The screen is read-only and about one account. There is deliberately no
 * comparison with colleagues, although the tenant model (ADR 0060) would make
 * one possible: a trainer that ranks employees against each other is a
 * different product with a different legal footing.
 */
export default function ProgressView() {
  const { sessions, state, truncated, total } = useProgressData();
  const { focus } = useFocusContext();
  const { consent } = useConsentContext();
  // "Gesamt" by default: in the pilot a 30-day window is usually empty, and an
  // empty screen on arrival teaches the user that there is nothing here.
  const [period, setPeriod] = useState<PeriodKey>("all");

  const days = PERIODS.find((p) => p.key === period)?.days ?? null;
  const inPeriod = withinPeriod(sessions, days);
  // The call length rides along with the measured Kennzahlen. It is derived
  // from the two timestamps rather than measured from the audio, but it belongs
  // to the same family: descriptive, and in need of no norm to be readable.
  const duration = durationSeries(inPeriod);
  const series = [...toSeries(inPeriod), ...(duration ? [duration] : [])];
  const counts = activity(inPeriod);
  const goals = pickedGoals(focus?.goals ?? [], focus?.selected ?? []);

  if (state === "loading") {
    return (
      <Frame>
        <p className="muted">Ihre Trainings werden geladen …</p>
      </Frame>
    );
  }

  if (state === "failed") {
    return (
      <Frame>
        <div className="card">
          <p>Ihre Trainings konnten nicht geladen werden. Bitte versuchen Sie es später erneut.</p>
        </div>
      </Frame>
    );
  }

  // Nothing stored and nothing being stored: the dashboard cannot fill up on
  // its own, and saying "noch keine Trainings" would send the user off to train
  // when the reason is a setting.
  if (sessions.length === 0 && consent && !consent.allows_storage) {
    return (
      <Frame>
        <div className="card">
          <h2>Ohne Speicherung entsteht kein Verlauf</h2>
          <p>
            Sie haben der Speicherung Ihrer Trainings nicht zugestimmt. Trainieren können Sie
            weiterhin uneingeschränkt, aber es wird nichts abgelegt, woraus sich ein Verlauf
            ergeben könnte.
          </p>
          <p>
            <Link to={ROUTES.profile}>Einstellung im Profil ändern</Link>
          </p>
        </div>
      </Frame>
    );
  }

  if (sessions.length === 0) {
    return (
      <Frame>
        <EmptyState goals={goals} />
      </Frame>
    );
  }

  return (
    <Frame>
      <div className="progress-head">
        {/* Three counted facts as figures rather than one sentence. Activity
            needs no norm to be readable (ADR 0065 says so outright), so it is
            the one thing on this screen that can lead with a number and no
            caveat -- which is exactly what gives the page something to open
            with. */}
        <ul className="progress-facts">
          <li>
            <span className="progress-fact-figure">{counts.sessions}</span>
            <span className="progress-fact-label">
              {counts.sessions === 1 ? "Training" : "Trainings"}
              {counts.firstAt && counts.lastAt && (
                <span className="progress-fact-span">
                  {formatDate(counts.firstAt)} bis {formatDate(counts.lastAt)}
                </span>
              )}
            </span>
          </li>
          <li>
            <span className="progress-fact-figure">{counts.scenarios}</span>
            <span className="progress-fact-label">
              {counts.scenarios === 1 ? "Szenario" : "Szenarien"}
            </span>
          </li>
          <li>
            <span className="progress-fact-figure">{counts.personas}</span>
            <span className="progress-fact-label">
              {counts.personas === 1 ? "Gesprächspartner" : "Gesprächspartner"}
            </span>
          </li>
        </ul>

        <div className="progress-periods" role="group" aria-label="Zeitraum">
          {PERIODS.map((option) => (
            <button
              type="button"
              key={option.key}
              className={`progress-period${option.key === period ? " is-active" : ""}`}
              aria-pressed={option.key === period}
              onClick={() => setPeriod(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {truncated && (
        <p className="muted progress-note">
          Gezeigt werden Ihre {sessions.length} neuesten Trainings von insgesamt {total}.
        </p>
      )}

      {/* Activity first, because it is the one thing that says something from
          the very first training onwards, while the Kennzahlen need a handful
          of calls before they carry anything.

          The calendar sits outside the period check and reads every stored
          training: it pages through months on its own, so the switch above
          would only ever take months away from it. */}
      <section className="progress-section">
        <div className="progress-columns">
          <div className="card progress-activity-card">
            <h2>Wann Sie trainiert haben</h2>
            <ActivityCalendar sessions={sessions} />
          </div>

          <div className="card progress-variety-card">
            <h2>Womit Sie trainiert haben</h2>
            {inPeriod.length === 0 ? (
              <p className="muted">In diesem Zeitraum liegt kein Training.</p>
            ) : (
              <>
                <VarietyGrid variety={variety(inPeriod)} />
                <p className="focus-tile-note">
                  Wie oft Sie welches Szenario mit welchem Gesprächspartner gespielt haben.
                </p>
              </>
            )}
          </div>
        </div>
      </section>

      {inPeriod.length === 0 ? (
        <div className="card">
          <p>
            In diesem Zeitraum liegt kein Training. Wählen Sie oben einen größeren Zeitraum.
          </p>
        </div>
      ) : (
        <>
          {goals.length > 0 ? (
            <FocusSection
              goals={goals}
              series={series}
              sessionCount={inPeriod.length}
              sessions={inPeriod}
            />
          ) : (
            <OverviewSection series={series} />
          )}

          <MetricSection series={series} sessionCount={inPeriod.length} />

          <ProgressRecurring sessions={inPeriod} catalogue={focus?.goals ?? []} />

          <ProgressPractice sessions={inPeriod} catalogue={focus?.goals ?? []} />
        </>
      )}
    </Frame>
  );
}

/** The page frame, so every branch above returns the same heading and back link
 *  instead of each repeating them. */
function Frame({ children }: { children: ReactNode }) {
  return (
    <AppLayout wide progressActive pageClassName="app-page-wide progress-page">
      <h1>Ihr Fortschritt</h1>
      <p className="page-lead">
        Ihre eigenen Werte über die Zeit. Sie werden hier nicht bewertet: Für keine dieser
        Größen gibt es einen belegten Richtwert, an dem sie zu messen wäre.
      </p>
      {children}
    </AppLayout>
  );
}

// --- Focus goals (block B) ---------------------------------------------------

/** The picked goals, in catalogue order, resolved against the catalogue. A key
 *  whose goal has since been retired simply drops out. */
function pickedGoals(catalogue: FocusGoal[], selected: string[]): FocusGoal[] {
  return catalogue.filter((goal) => selected.includes(goal.key));
}

function FocusSection({
  goals,
  series,
  sessionCount,
  sessions,
}: {
  goals: FocusGoal[];
  series: MetricSeries[];
  sessionCount: number;
  /** For the goals with no measurement of their own, which are answered by how
   *  often the wrap-ups named them. */
  sessions: SessionSummary[];
}) {
  return (
    <section className="progress-section">
      <div className="progress-section-head">
        <h2>Ihre Fokusziele</h2>
        <Link to={ROUTES.profile} className="progress-section-link">
          Ziele ändern
        </Link>
      </div>

      <ul className="focus-tiles">
        {goals.map((goal) => (
          <li key={goal.key}>
            <FocusTile
              goal={goal}
              series={series}
              sessionCount={sessionCount}
              sessions={sessions}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * One focus goal.
 *
 * Three shapes, because the honest answer differs per goal (see
 * `utils/focusMetrics.ts`): a Kennzahl with its course, an activity figure, or
 * the plain statement that this goal has no measurement yet. The third is
 * deliberately not hidden. A tile that quietly disappears would let the user
 * believe the goal is being tracked.
 */
function FocusTile({
  goal,
  series,
  sessionCount,
  sessions,
}: {
  goal: FocusGoal;
  series: MetricSeries[];
  sessionCount: number;
  sessions: SessionSummary[];
}) {
  const backing = backingOf(goal.key);
  const primary = series.find((s) => s.key === backing.metrics[0]);

  return (
    <div className="focus-tile">
      <h3 className="focus-tile-title">{goal.title}</h3>

      {backing.kind === "metric" && primary ? (
        <MetricBody series={primary} sessionCount={sessionCount} />
      ) : backing.kind === "segment" ? (
        <SegmentBody sessions={sessions} />
      ) : backing.kind === "activity" ? (
        <p className="focus-tile-note">
          {goal.key === "training_regularity"
            ? `${sessionCount} ${sessionCount === 1 ? "Training" : "Trainings"} im gewählten Zeitraum.`
            : "Wie breit Sie trainieren, sehen Sie an den Szenarien und Gesprächspartnern oben."}
        </p>
      ) : (
        <GoalMentionBody goal={goal.key} sessions={sessions} note={backing.note} />
      )}

      {/* One drill-down per tile, and it is the goal's own page rather than a
          Kennzahl's: a tile stands for a goal, and the goals with no
          measurement need the level most. That page links on to the chart
          where there is one, and the Kennzahlen grid below still reaches the
          charts in one click. Activity goals have none -- what answers them is
          the two figures at the top of this very screen. */}
      {backing.kind !== "activity" && (
        <Link className="progress-detail-link" to={progressGoalPath(goal.key)}>
          Was dazu gesagt wurde
        </Link>
      )}
    </div>
  );
}

/**
 * The tile of a goal answered by a comparison rather than by a series
 * (ADR 0081): how somebody spoke while the other side pushed back, against the
 * rest of the call.
 *
 * A count of trainings and nothing else here. The comparison itself is two
 * figures per Kennzahl per training, which is a table and not a tile, so it
 * lives one level down; and any single number this tile could show instead --
 * an average gap, a "stability" -- would be the composite ADR 0051 refuses.
 */
function SegmentBody({ sessions }: { sessions: SessionSummary[] }) {
  const withComparison = segmentTrainings(sessions).length;

  if (withComparison === 0) {
    return (
      <p className="focus-tile-note">
        Noch kein Training mit einer fordernden Passage. Gemessen wird der Vergleich erst,
        wenn Ihr Gegenüber im Gespräch widersprochen oder nachgehakt hat.
      </p>
    );
  }

  return (
    <>
      <p className="progress-metric-figure">{withComparison}</p>
      <p className="focus-tile-note">
        {withComparison === 1 ? "Ein Training" : `${withComparison} Trainings`} mit einer
        fordernden Passage. Verglichen wird dort, wie Sie unter Druck gesprochen haben und
        wie sonst.
      </p>
    </>
  );
}

/**
 * A goal that has no measurement of its own, answered by what the wrap-ups
 * said about it.
 *
 * Six of the fourteen goals are like this, and four of them always will be:
 * whether a close was clear is in what was said, and no acoustic figure will
 * ever reach it. Counting the mentions is the honest substitute, and the
 * wording keeps it a count of statements rather than a verdict.
 *
 * No threshold here, unlike the recurring block, which needs two mentions
 * before it calls something a pattern. On a tile the user picked themselves,
 * "once so far" is a legitimate answer to "how is this going"; in a list of
 * recurring themes it would be noise.
 */
function GoalMentionBody({
  goal,
  sessions,
  note,
}: {
  goal: string;
  sessions: SessionSummary[];
  /** What to say when the wrap-ups have said nothing about this goal yet.
   *  Undefined for the goals `focusMetrics` files under another kind, which
   *  never reach this component. */
  note: string | undefined;
}) {
  const { strengths, improvements, total } = mentionsFor(sessions, goal);

  if (total === 0 || (strengths === 0 && improvements === 0)) {
    return <p className="focus-tile-note">{note}</p>;
  }

  return (
    <>
      <p className="progress-metric-figure">
        {improvements > 0 ? `${improvements} von ${total}` : `${strengths} von ${total}`}
      </p>
      <p className="focus-tile-note">
        {improvements > 0
          ? `In ${improvements} von ${total} ausgewerteten Trainings als Verbesserungspunkt genannt`
          : `In ${strengths} von ${total} ausgewerteten Trainings als Stärke genannt`}
        {improvements > 0 && strengths > 0 && `, in ${strengths} als Stärke`}. Zu diesem Ziel gibt
        es keine Messung. Gezählt wird, was Ihre Auswertungen geschrieben haben.
      </p>
    </>
  );
}

/** A metric's current state: the last value, its course, and the user's own
 *  usual range in words. Shared by the focus tiles and the metric grid. */
function MetricBody({
  series,
  sessionCount,
  interactive = true,
}: {
  series: MetricSeries;
  sessionCount: number;
  /** Off inside a link: a hover layer nested in an anchor fights it for the
   *  pointer, and the whole cell is the target there. */
  interactive?: boolean;
}) {
  const last = series.points[series.points.length - 1];

  if (series.points.length < MIN_SESSIONS_FOR_SERIES) {
    return (
      <>
        <p className="progress-metric-figure">
          {last ? formatValue(last.value, series.unit) : "noch kein Wert"}
        </p>
        <p className="focus-tile-note">
          Ab {MIN_SESSIONS_FOR_SERIES} Trainings wird hier der Verlauf gezeigt. Bisher{" "}
          {series.points.length} von {sessionCount}.
        </p>
      </>
    );
  }

  return (
    <>
      <p className="progress-metric-figure">
        {last ? formatValue(last.value, series.unit) : ""}
        <span className="progress-metric-figure-label"> zuletzt</span>
      </p>
      <Sparkline series={series} interactive={interactive} />
      <p className="focus-tile-note">
        Ihr üblicher Bereich {formatValue(series.band?.low ?? 0, null)} bis{" "}
        {formatValue(series.band?.high ?? 0, series.unit)}, aus {series.points.length}{" "}
        Trainings.
      </p>
    </>
  );
}

// --- Replacement when no goals are picked (block B') -------------------------

/**
 * What stands where the focus goals would be when none are set.
 *
 * Not an empty box and not a nag. The three Kennzahlen that moved most across
 * the period are the ones where there is something to look at, so they earn the
 * space; the invitation to pick goals sits beside them as an offer. Choosing
 * goals is voluntary (F-62) and a screen that withholds content until you do
 * would make it less so.
 */
function OverviewSection({ series }: { series: MetricSeries[] }) {
  const withSpread = series
    .filter((s) => s.points.length >= MIN_SESSIONS_FOR_SERIES && s.band)
    .map((s) => ({
      series: s,
      // Relative spread, so a Redeanteil in percent and a Reaktionszeit in
      // seconds can be compared at all.
      spread: s.band ? (s.band.high - s.band.low) / (Math.abs(s.band.median) || 1) : 0,
    }))
    .sort((a, b) => b.spread - a.spread)
    .slice(0, 3);

  return (
    <section className="progress-section">
      <div className="progress-section-head">
        <h2>Überblick</h2>
      </div>

      {withSpread.length > 0 ? (
        <ul className="focus-tiles">
          {withSpread.map(({ series: s }) => (
            <li key={s.key}>
              <div className="focus-tile">
                <h3 className="focus-tile-title">{s.name}</h3>
                <MetricBody series={s} sessionCount={s.points.length} />
                <Link className="progress-detail-link" to={progressMetricPath(s.key)}>
                  Einzelne Trainings ansehen
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="card">
          <p>Für einen Überblick fehlen noch Trainings. Die Zahlen unten sind schon da.</p>
        </div>
      )}

      <div className="card progress-invite">
        <p>
          <strong>Sie haben keine Fokusziele gesetzt.</strong> Mit Fokuszielen steht an dieser
          Stelle, woran Sie gerade arbeiten. Trainiert wird ohnehin alles.
        </p>
        <Link to={ROUTES.profile} className="consent-button consent-button-secondary">
          Fokusziele wählen
        </Link>
      </div>
    </section>
  );
}

// --- All Kennzahlen (block C) ------------------------------------------------

/**
 * Every Kennzahl over time, one half of them at a time.
 *
 * The switch is the reason this block is readable at all. Ten charts of equal
 * size side by side is a wall: nothing leads, nothing is worth stopping at, and
 * the screen reads as a report somebody has to work through. Five is a group
 * the eye takes in at once.
 *
 * `FilterSlider` and not a set of tabs, because the application already
 * switches two other things this way (the Scenario library's two filter rows,
 * the Kennzahlen after a call) and a third pattern for the same act would be a
 * third thing to learn. The split is the schema's own `aspect`, so it matches
 * the one the post-call screen uses and no mapping is invented here.
 */
function MetricSection({
  series,
  sessionCount,
}: {
  series: MetricSeries[];
  sessionCount: number;
}) {
  const [half, setHalf] = useState<MetricAspect>("how");

  if (series.length === 0) {
    return (
      <section className="progress-section">
        <h2>Kennzahlen über die Zeit</h2>
        <div className="card">
          <p>
            Zu den Trainings in diesem Zeitraum liegen keine Kennzahlen vor. Das kommt vor,
            wenn ein Gespräch sehr kurz war oder die Messung nicht durchlief.
          </p>
        </div>
      </section>
    );
  }

  const halves: { value: MetricAspect; label: string }[] = [
    { value: "how", label: GROUPS.speech.label },
    { value: "what", label: GROUPS.content.label },
  ];
  const options = halves.map((option) => ({
    ...option,
    count: series.filter((s) => groupOf(s.aspect) === groupOf(option.value)).length,
  }));
  const shown = series.filter((s) => groupOf(s.aspect) === groupOf(half));

  return (
    <section className="progress-section">
      <div className="progress-section-head">
        <h2>
          {/* The family's hue, said once here rather than on each of the six
              tiles below, which under this switch all belong to it. */}
          <span
            className="progress-group-dot"
            style={{ "--series": GROUPS[groupOf(half)].color } as CSSProperties}
            aria-hidden="true"
          />
          Kennzahlen über die Zeit
        </h2>
        <FilterSlider
          options={options}
          value={half}
          onChange={setHalf}
          label="Welche Kennzahlen"
        />
      </div>

      {/* Small multiples: same size, same shape, so the eye compares them
          instead of reading each one on its own terms. */}
      <ul className="progress-metric-grid">
        {shown.map((s) => (
          <li key={s.key}>
            <Link className="progress-metric-cell" to={progressMetricPath(s.key)}>
              <span className="progress-metric-cell-name">{s.name}</span>
              <MetricBody series={s} sessionCount={sessionCount} interactive={false} />
            </Link>
          </li>
        ))}
      </ul>

      <p className="muted progress-note">
        {half === "how"
          ? "Wie Sie gesprochen haben: Tempo, Pausen, Lautstärke, Sprachmelodie."
          : "Worüber gesprochen wurde: Redeanteil, Fragen, Wortanzahl, Dauer."}{" "}
        Die Farbe steht für die Gruppe, nie für einen Wert.
      </p>
    </section>
  );
}

// --- Nothing stored yet ------------------------------------------------------

function EmptyState({ goals }: { goals: FocusGoal[] }) {
  return (
    <>
      <div className="card">
        <h2>Noch kein Training abgeschlossen</h2>
        <p>
          Sobald Sie ein Gespräch zu Ende geführt haben, stehen hier Ihre Kennzahlen und ihr
          Verlauf über die Zeit. Ein Verlauf wird ab {MIN_SESSIONS_FOR_SERIES} Trainings
          gezeigt, vorher wären es einzelne Punkte ohne Aussage.
        </p>
        <Link to={ROUTES.training} className="consent-button consent-button-primary">
          Training starten
        </Link>
      </div>

      {goals.length > 0 && (
        <section className="progress-section">
          <h2>Ihre Fokusziele</h2>
          <p className="muted">
            Diese Ziele haben Sie gewählt. Sie werden hier ausgewertet, sobald Trainings
            vorliegen.
          </p>
          <ul className="focus-summary">
            {goals.map((goal) => (
              <li key={goal.key}>{goal.title}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
