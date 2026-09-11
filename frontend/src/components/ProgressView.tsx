import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { useFocusContext } from "../FocusContext";
import { useProgressData } from "../hooks/useProgressData";
import type { FocusGoal, SessionSummary } from "../protocol";
import { ROUTES, progressGoalPath, progressMetricPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import { mentionsFor } from "../utils/goalMentions";
import { segmentTrainings } from "../utils/segmentStats";
import {
  MIN_SESSIONS_FOR_SERIES,
  activity,
  durationSeries,
  formatPoint,
  formatBand,
  variety,
  latest,
  toSeries,
  type MetricSeries,
} from "../utils/progressStats";
import { formatDate } from "../utils/time";
import ActivityCalendar from "./ActivityCalendar";
import AppLayout from "./AppLayout";
import InfoDetails from "./InfoDetails";
import MentionTally from "./MentionTally";
import PartsStrip, { partsSummary } from "./PartsStrip";
import ProgressMetricTable from "./ProgressMetricTable";
import ProgressPractice from "./ProgressPractice";
import ProgressRecurring from "./ProgressRecurring";
import Sparkline from "./Sparkline";
import VarietyGrid from "./VarietyGrid";

/**
 * Kennzahlen that stay out of the overview, though their own page and the
 * focus goals still reach them.
 *
 * `word_count` grows with the length of the call and with nothing else worth
 * reading across trainings, so its row would repeat the Gesprächsdauer beside
 * it in other units. It is still measured and still listed under "Prägnante
 * Sprache".
 *
 * The loudness is not here because it never reaches this screen at all:
 * `progressStats.NOT_ACROSS_CALLS` drops it before any series is built.
 */
const OVERVIEW_HIDDEN = new Set(["word_count"]);

/**
 * Which trainings the screen is read over, counted in trainings (see
 * `progressStats.latest` for why not in days).
 *
 * It used to be 30 days, six months and "Gesamt". Six months is the retention
 * limit (ADR 0067), so the second and third said the same thing on almost
 * every account, and the first was empty for anybody who trains in bursts.
 * "Alle" is still everything stored and nothing older.
 */
const PERIODS = [
  { key: "5", label: "Letzte 5", count: 5 },
  { key: "10", label: "Letzte 10", count: 10 },
  { key: "all", label: "Alle", count: null },
] as const;

type PeriodKey = (typeof PERIODS)[number]["key"];

/**
 * The progress dashboard (F-13, docs/dashboard-konzept.md).
 *
 * Top to bottom: where am I going (the focus goals), what next (what the
 * wrap-ups keep coming back to, with the one thing to practise beside it), how
 * am I going (every Kennzahl over time), and last what I did (the calendar and
 * the variety grid). The first three are Hattie & Timperley's feed up, feed
 * forward and feed back; the order puts the one block that leads back into
 * training second rather than last, because a dashboard whose only way out is
 * at the bottom of its longest page ends in looking (Zimmerman's reflection
 * phase has to hand over to planning, dashboard-konzept.md section 3). The
 * activity blocks moved down for the same reason: they are context, and they
 * were the first thing on the page only because in the pilot there was little
 * else to show.
 *
 * The recurring themes and the suggestion used to be a labelled placeholder;
 * they became real once each feedback point carried the focus goal it was
 * about (ADR 0080) -- `ProgressRecurring` counts what recurs,
 * `ProgressPractice` turns the most frequent improvement into a single
 * suggestion with a button, and the two now share one row.
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
  // Everything by default, as dashboard-konzept.md section 10 decided: the
  // first look should show all there is, and narrowing is one click away.
  const [period, setPeriod] = useState<PeriodKey>("all");

  const count = PERIODS.find((p) => p.key === period)?.count ?? null;
  const inPeriod = latest(sessions, count);
  // The call length rides along with the measured Kennzahlen. It is derived
  // from the two timestamps rather than measured from the audio, but it belongs
  // to the same family: descriptive, and in need of no norm to be readable.
  const duration = durationSeries(inPeriod);
  const series = [...toSeries(inPeriod), ...(duration ? [duration] : [])];
  const overview = series.filter((s) => !OVERVIEW_HIDDEN.has(s.key));
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

        <div className="progress-periods" role="group" aria-label="Welche Trainings">
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

      {/* No "nothing in this period" branch any more: counted in trainings,
          the selection is never empty while anything is stored, and the case
          of nothing stored returned above. */}
      {goals.length > 0 ? (
        <FocusSection
          goals={goals}
          series={series}
          sessionCount={inPeriod.length}
          sessions={inPeriod}
          allSessions={sessions}
        />
      ) : (
        <OverviewSection series={overview} />
      )}

      {/* Second, directly under the goals: what the wrap-ups keep naming, and
          beside the improvements the one call to practise them in. It is the
          only block on the page that leads back into training, and it used to
          be the last one. */}
      <ProgressRecurring
        sessions={inPeriod}
        catalogue={focus?.goals ?? []}
        practice={<ProgressPractice sessions={inPeriod} catalogue={focus?.goals ?? []} />}
      />

      <ProgressMetricTable series={overview} />

      {/* Last, as context. The calendar sits outside the period check and reads
          every stored training: it pages through months on its own, so the
          switch above would only ever take months away from it. The variety
          grid beside it does follow the switch. */}
      <section className="progress-section" aria-labelledby="activity-title">
        <div className="progress-section-head">
          <h2 id="activity-title">Ihr Training</h2>
        </div>
        <div className="progress-columns">
          <div className="card progress-activity-card">
            <h3 className="progress-card-title">Wann Sie trainiert haben</h3>
            <ActivityCalendar sessions={sessions} />
          </div>

          <div className="card progress-variety-card">
            <h3 className="progress-card-title">Womit Sie trainiert haben</h3>
            <VarietyGrid variety={variety(inPeriod)} />
            <p className="focus-tile-note">
              Wie oft Sie welches Szenario mit welchem Gesprächspartner gespielt haben.
            </p>
          </div>
        </div>
      </section>
    </Frame>
  );
}

/** The page frame, so every branch above returns the same heading and back link
 *  instead of each repeating them. */
function Frame({ children }: { children: ReactNode }) {
  return (
    <AppLayout wide progressActive pageClassName="app-page-wide progress-page">
      <h1>Ihr Fortschritt</h1>
      {/* What the page is, first, and that nothing on it is a grade, in one
          sentence -- that half cannot move behind the "i": a reader who is not
          told that no figure is judged fills the gap in and assumes higher is
          better (dashboard-konzept.md section 2). The reason why belongs
          behind it. */}
      <p className="page-lead">
        Woran Sie arbeiten, was Ihre Auswertungen wiederholt nennen und wie Sie über Ihre
        Trainings hinweg gesprochen haben. Bewertet wird hier nichts.
      </p>
      <InfoDetails label="Warum hier nichts bewertet wird">
        <p>
          Für keine dieser Größen gibt es einen belegten Richtwert, an dem sie für Ihre
          Gespräche zu messen wäre. Ein Redeanteil von 60 % kann in einem Beratungsgespräch
          genau richtig und in einer Beschwerde zu viel sein. Deshalb zeigt diese Seite Ihre
          eigenen Werte und den Bereich, in dem sie meistens liegen, aber keine Zielwerte,
          keine Farben für gut oder schlecht und keine Pfeile.
        </p>
        <p>
          Gezeigt werden nur Ihre eigenen Trainings. Einen Vergleich mit anderen gibt es nicht
          und wird es nicht geben.
        </p>
      </InfoDetails>
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
  allSessions,
}: {
  goals: FocusGoal[];
  series: MetricSeries[];
  sessionCount: number;
  /** For the goals with no measurement of their own, which are answered by how
   *  often the wrap-ups named them. */
  sessions: SessionSummary[];
  /** Everything stored, whatever the switch says (see `FocusTile`). */
  allSessions: SessionSummary[];
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
              allSessions={allSessions}
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
 * Four shapes, because the honest answer differs per goal (see
 * `utils/focusMetrics.ts`): Kennzahlen with their course, a comparison of two
 * stretches of a call, an activity figure, or what the wrap-ups said where
 * there is no measurement. The last is deliberately not hidden. A tile that
 * quietly disappears would let the user believe the goal is being tracked.
 */
function FocusTile({
  goal,
  series,
  sessionCount,
  sessions,
  allSessions,
}: {
  goal: FocusGoal;
  series: MetricSeries[];
  sessionCount: number;
  sessions: SessionSummary[];
  /** Every stored training, for the regularity goal, which is about the
   *  calendar and not about the trainings the switch selected. */
  allSessions: SessionSummary[];
}) {
  const backing = backingOf(goal.key);
  const primary = series.find((s) => s.key === backing.metrics[0]);
  const supporting = backing.metrics
    .slice(1)
    .filter((key) => !OVERVIEW_HIDDEN.has(key))
    .map((key) => series.find((s) => s.key === key))
    .filter((s): s is MetricSeries => s !== undefined)
    .slice(0, MAX_SUPPORTING);

  return (
    <div className="focus-tile">
      <h3 className="focus-tile-title">{goal.title}</h3>

      {backing.kind === "metric" && primary ? (
        <>
          <MetricBody series={primary} sessionCount={sessionCount} />
          {supporting.length > 0 && <SupportingMetrics series={supporting} />}
        </>
      ) : backing.kind === "segment" ? (
        <SegmentBody sessions={sessions} />
      ) : backing.kind === "activity" ? (
        <p className="focus-tile-note">
          {goal.key === "training_regularity"
            ? regularityText(allSessions)
            : "Wie breit Sie trainieren, zeigt das Raster unter „Ihr Training“."}
        </p>
      ) : (
        <GoalMentionBody goal={goal.key} sessions={sessions} note={backing.note} />
      )}

      {/* One drill-down per tile, and it is the goal's own page rather than a
          Kennzahl's: a tile stands for a goal, and the goals with no
          measurement need the level most. That page links on to the chart
          where there is one, and the Kennzahlen table below still reaches the
          charts in one click. Activity goals have none -- what answers them is
          the calendar and the variety grid on this very screen. */}
      {backing.kind !== "activity" && (
        <Link className="progress-detail-link" to={progressGoalPath(goal.key)}>
          Was dazu gesagt wurde
        </Link>
      )}
    </div>
  );
}

/** How many of a goal's further Kennzahlen stand on its tile under the first.
 *  Two: `pace` and `active_listening` name three between them, which together
 *  are the goal, and a third line would turn the tile into the table below. */
const MAX_SUPPORTING = 2;

/**
 * The goal's other Kennzahlen, one line each: name, the last value, a small
 * course.
 *
 * The first Kennzahl alone told half the story. Sprechtempo, Sprechpausen and
 * Sprechlänge am Stück are together the rhythm of somebody's speaking, and each
 * can look unchanged while the rhythm moves (`focusMetrics.FOCUS_BACKING`). So
 * the tile carries the rest too, smaller, in the same hue and on the same
 * terms: no band, no colour for a value, the figure printed beside the line.
 */
function SupportingMetrics({ series }: { series: MetricSeries[] }) {
  return (
    <ul className="focus-supporting">
      {series.map((s) => {
        const last = s.points[s.points.length - 1];
        return (
          <li key={s.key} className="focus-supporting-row">
            <span className="focus-supporting-name">{s.name}</span>
            <span className="focus-supporting-value">
              {last ? formatPoint(s, last.value) : "–"}
            </span>
            {s.shape === "line" && s.points.length >= MIN_SESSIONS_FOR_SERIES && (
              <span className="focus-supporting-course">
                <Sparkline series={s} height={22} showDots={false} interactive={false} />
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Regular training in words: how many trainings in the last 30 days, and when
 *  the last one was. A count and a date, no verdict on either -- how often is
 *  often enough is exactly the kind of number nobody has established. */
function regularityText(sessions: SessionSummary[]): string {
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const completed = sessions.filter((s) => s.status === "completed");
  const recent = completed.filter((s) => new Date(s.started_at).getTime() >= cutoff).length;
  const last = completed[0]?.started_at;
  const count = `${recent} ${recent === 1 ? "Training" : "Trainings"} in den letzten 30 Tagen`;
  return last ? `${count}, zuletzt am ${formatDate(last) ?? last}.` : `${count}.`;
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

  // Pips and a count in small type, the way the recurring block draws the same
  // kind of statement. The large figure this used to lead with made "3 von 8"
  // the most prominent thing on the tile, and in display type a count over a
  // denominator reads as a mark (`MentionTally`).
  return (
    <>
      <ul className="focus-mentions">
        {improvements > 0 && (
          <li>
            <span className="focus-mentions-label">Als Verbesserung genannt</span>
            <MentionTally count={improvements} total={total} />
            <span className="focus-mentions-count">
              {improvements} von {total}
            </span>
          </li>
        )}
        {strengths > 0 && (
          <li>
            <span className="focus-mentions-label">Als Stärke genannt</span>
            <MentionTally count={strengths} total={total} />
            <span className="focus-mentions-count">
              {strengths} von {total}
            </span>
          </li>
        )}
      </ul>
      <p className="focus-tile-note">
        Keine Messung. Gezählt wird, in wie vielen ausgewerteten Trainings es genannt wurde.
      </p>
    </>
  );
}

/** A metric's current state: the last value, its course, and the user's own
 *  usual range in words. Shared by the focus tiles and the overview that
 *  stands in for them. */
function MetricBody({ series, sessionCount }: { series: MetricSeries; sessionCount: number }) {
  const last = series.points[series.points.length - 1];

  // A checklist has no course and no band (see `SeriesShape`): the counts per
  // training, and how often all parts were there.
  if (series.shape === "parts") {
    const summary = partsSummary(series);
    return (
      <>
        <p className="progress-metric-figure">
          {last ? formatPoint(series, last.value) : "noch kein Wert"}
          {last && <span className="progress-metric-figure-label"> zuletzt</span>}
        </p>
        <PartsStrip series={series} />
        {summary && <p className="focus-tile-note">{summary}.</p>}
      </>
    );
  }

  if (series.points.length < MIN_SESSIONS_FOR_SERIES) {
    return (
      <>
        <p className="progress-metric-figure">
          {last ? formatPoint(series, last.value) : "noch kein Wert"}
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
        {last ? formatPoint(series, last.value) : ""}
        <span className="progress-metric-figure-label"> zuletzt</span>
      </p>
      <Sparkline series={series} />
      <p className="focus-tile-note">
        Ihr üblicher Bereich {formatBand(series) ?? "–"}, aus {series.points.length} Trainings.
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
