import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { useFocusContext } from "../FocusContext";
import { OCCASIONS, PERIODS, useProgressContext } from "../ProgressContext";
import type { FocusGoal, SessionSummary } from "../protocol";
import { ROUTES, progressGoalPath, progressMetricPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import { mentionsFor, statementsFor } from "../utils/goalMentions";
import { showsInOverview } from "../utils/metrics";
import { downloadProgressPdf } from "../utils/progressPdf";
import { segmentTrainings } from "../utils/segmentStats";
import {
  MIN_SESSIONS_FOR_SERIES,
  mostVarying,
  activity,
  formatPoint,
  formatBand,
  variety,
  partsSummary,
  type MetricSeries,
} from "../utils/progressStats";
import { formatDate } from "../utils/time";
import ActivityCalendar from "./ActivityCalendar";
import AppLayout from "./AppLayout";
import InfoDetails from "./InfoDetails";
import MentionTally from "./MentionTally";
import PartsStrip from "./PartsStrip";
import ProgressMetricTable from "./ProgressMetricTable";
import ProgressPractice from "./ProgressPractice";
import ProgressRecurring from "./ProgressRecurring";
import SectionHeading from "./SectionHeading";
import Sparkline from "./Sparkline";
import VarietyGrid from "./VarietyGrid";

/**
 * Progress dashboard (F-13, docs/dashboard-concept.md): activity over every training, then the period switch
 * (placed where its reach begins; kept in the URL, `ProgressContext`), then goals, recurring themes and metrics
 * over the selection. Nothing evaluated (ADR 0065, ADR 0051); no comparison with colleagues (ADR 0060 would allow).
 */
export default function ProgressView() {
  // The trainings and the selection both come from the provider, which the two
  // detail levels read as well — that is what keeps a tile and the page behind
  // it talking about the same set (see ProgressContext.tsx). `withPeriod` is
  // not taken here: the links that need it sit in the tiles and in the metric
  // table, which read it from the same context.
  const {
    sessions,
    selected: inPeriod,
    series,
    state,
    truncated,
    total,
    period,
    setPeriod,
    occasion,
    setOccasion,
    occasionCounts,
  } = useProgressContext();
  const { focus } = useFocusContext();
  const { consent } = useConsentContext();
  const overview = series.filter((s) => showsInOverview(s.key));
  // Over everything stored, like the calendar they stand beside: the three
  // figures sit above the switch now, so they cannot follow it.
  const counts = activity(sessions);
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
  // its own, and reporting an empty history would send the user off to train
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
      {truncated && (
        <p className="muted progress-note">
          Gezeigt werden Ihre {sessions.length} neuesten Trainings von insgesamt {total}.
        </p>
      )}

      {/* First, above the switch: activity over every stored training. It needs no norm (ADR 0065) and is
          what a returning User checks first. */}
      <section className="progress-section progress-training-section" aria-labelledby="activity-title">
        <SectionHeading id="activity-title" eyebrow="WAS SIE GETAN HABEN" title="Ihr Training" />

        <div className="progress-training">
          <ul className="progress-stats">
            <li className="card progress-stat">
              <span className="progress-stat-figure">{counts.sessions}</span>
              <span className="progress-stat-label">
                {counts.sessions === 1 ? "Training" : "Trainings"}
              </span>
              {counts.firstAt && counts.lastAt && (
                <span className="progress-stat-span">
                  {formatDate(counts.firstAt)} bis {formatDate(counts.lastAt)}
                </span>
              )}
            </li>
            <li className="card progress-stat">
              <span className="progress-stat-figure">{counts.scenarios}</span>
              <span className="progress-stat-label">
                {counts.scenarios === 1 ? "Szenario" : "Szenarien"}
              </span>
            </li>
            <li className="card progress-stat">
              <span className="progress-stat-figure">{counts.personas}</span>
              <span className="progress-stat-label">Gesprächspartner</span>
            </li>
          </ul>

          <div className="card">
            <h3 className="progress-card-title">Wann Sie trainiert haben</h3>
            <ActivityCalendar sessions={sessions} />
          </div>

          <div className="card">
            <h3 className="progress-card-title">Womit Sie trainiert haben</h3>
            <VarietyGrid variety={variety(sessions)} sessions={sessions} />
            <p className="focus-tile-note">
              Wie oft Sie welches Szenario mit welchem Gesprächspartner gespielt haben.
            </p>
          </div>
        </div>
      </section>

      {/* The switch sits where its reach begins. Everything above it counts
          every stored training; everything below is read over the selection.
          It used to sit in the page head beside the counted facts, where it
          looked as if it governed them and the calendar too, and the calendar
          then needed a comment explaining why it did not. */}
      <div className="progress-scope">
        <span className="progress-scope-label" id="progress-scope-label">
          Ausgewertet werden
        </span>
        <div className="progress-periods" role="group" aria-labelledby="progress-scope-label">
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

        {/* Occasion filter, the same control as the period row. A course across different kinds of call is
            scatter, across one kind a series (concept section 4.3). Options carry their counts; an empty one
            cannot be pressed. */}
        <div
          className="progress-periods progress-occasions"
          role="group"
          aria-labelledby="progress-scope-label"
        >
          {OCCASIONS.map((option) => {
            const count = occasionCounts[option.key];
            return (
              <button
                type="button"
                key={option.key}
                className={`progress-period${option.key === occasion ? " is-active" : ""}`}
                aria-pressed={option.key === occasion}
                disabled={count === 0 && option.key !== occasion}
                onClick={() => setOccasion(option.key)}
              >
                {option.label}
                <span className="progress-period-count"> {count}</span>
              </button>
            );
          })}
        </div>

        <span className="progress-scope-note">
          {inPeriod.length} {inPeriod.length === 1 ? "Training" : "Trainings"}, für alles
          darunter
        </span>
      </div>

      {/* Empty only through the occasion row: counted in trainings, the period
          alone is never empty while anything is stored. Reachable by a shared
          link, and by deleting the last training of a kind while the filter is
          on it. */}
      {inPeriod.length === 0 ? (
        <div className="card">
          <p>
            Zu diesem Gesprächsanlass liegt in Ihrer Auswahl kein Training vor. Mit „Alle
            Anlässe“ steht hier wieder alles.
          </p>
        </div>
      ) : (
        <>
          {goals.length > 0 ? (
            <FocusSection
              goals={goals}
              series={series}
              sessions={inPeriod}
              allSessions={sessions}
            />
          ) : (
            <OverviewSection series={overview} />
          )}

          {/* Second, directly under the goals: what the wrap-ups keep naming,
              and beside the improvements the one call to practise them in. It
              is the only block on the page that leads back into training, and
              it used to be the last one. */}
          <ProgressRecurring
            sessions={inPeriod}
            catalogue={focus?.goals ?? []}
            practice={<ProgressPractice sessions={inPeriod} catalogue={focus?.goals ?? []} />}
          />

          <ProgressMetricTable series={overview} />
        </>
      )}

      {/* Last on the page, the way the feedback screen puts its download last:
          what to do once the reading is done, after the reading. It is offered
          even where the selection is empty, because the record at the top of
          the sheet counts every stored training and is worth having on its
          own. */}
      <DownloadReport />
    </Frame>
  );
}

/**
 * The whole screen as a PDF (F-13; `utils/progressPdf.ts`), counterpart of F-64's feedback file. Built in the
 * browser from the page's own numbers — a server route would be a second path to them (concept section 9).
 * Shares the feedback screen's actions-row classes rather than copying its rules.
 */
function DownloadReport() {
  const { sessions, selected, periodPhrase, truncated } = useProgressContext();
  const { focus } = useFocusContext();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  // Nothing to print before the first training, and the empty state above
  // already says what to do about that.
  if (sessions.length === 0) return null;

  const download = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await downloadProgressPdf({
        sessions,
        selected,
        phrase: periodPhrase,
        catalogue: focus?.goals ?? [],
        picked: focus?.selected ?? [],
        truncated,
      });
    } catch (e) {
      console.debug("[progress pdf] failed", e);
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="feedback-actions">
        <button type="button" className="back-to-start-button" disabled={busy} onClick={download}>
          {busy ? "PDF wird erstellt …" : "Fortschritt herunterladen"}
        </button>
      </div>

      {failed && (
        <p className="follow-up-error transcript-download-error">
          Das PDF konnte nicht erstellt werden. Bitte versuchen Sie es erneut.
        </p>
      )}
    </>
  );
}

/** The page frame, so every branch above returns the same heading and back link
 *  instead of each repeating them. */
function Frame({ children }: { children: ReactNode }) {
  return (
    <AppLayout progressActive pageClassName="app-page-wide progress-page">
      <h1>Ihr Fortschritt</h1>
      {/* What the page is, first, and that nothing on it is a grade, in one
          sentence -- that half cannot move behind the "i": a reader who is not
          told that no figure is judged fills the gap in and assumes higher is
          better (dashboard-concept.md section 2). The reason why belongs
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
  sessions,
  allSessions,
}: {
  goals: FocusGoal[];
  series: MetricSeries[];
  /** The trainings the switch selected. */
  sessions: SessionSummary[];
  /** Everything stored, whatever the switch says (see `FocusTile`). */
  allSessions: SessionSummary[];
}) {
  return (
    <section className="progress-section" aria-labelledby="focus-title">
      <SectionHeading
        id="focus-title"
        eyebrow="WORAN SIE ARBEITEN"
        title="Ihre Fokusziele"
        aside={
          <Link to={ROUTES.profile} className="progress-section-link">
            Ziele ändern
          </Link>
        }
      />

      <ul className="focus-tiles">
        {goals.map((goal) => (
          <li key={goal.key}>
            <FocusTile
              goal={goal}
              series={series}
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
 * One focus goal, in one of four shapes (`utils/focusMetrics.ts`): metrics with their course, a two-stretch
 * comparison, an activity figure, or wrap-up mentions. A goal with no measurement is shown, not hidden, or
 * the user would believe it is being tracked.
 */
function FocusTile({
  goal,
  series,
  sessions,
  allSessions,
}: {
  goal: FocusGoal;
  series: MetricSeries[];
  /** The trainings the switch selected. */
  sessions: SessionSummary[];
  /** Every stored training, for the regularity goal, which is about the
   *  calendar and not about the trainings the switch selected. */
  allSessions: SessionSummary[];
}) {
  const { withPeriod } = useProgressContext();
  const backing = backingOf(goal.key);
  const primary = series.find((s) => s.key === backing.metrics[0]);
  const supporting = backing.metrics
    .slice(1)
    .filter((key) => showsInOverview(key))
    .map((key) => series.find((s) => s.key === key))
    .filter((s): s is MetricSeries => s !== undefined)
    .slice(0, MAX_SUPPORTING);

  return (
    <div className="focus-tile">
      <h3 className="focus-tile-title">{goal.title}</h3>

      {backing.kind === "metric" && primary ? (
        <>
          <MetricBody series={primary} sessionCount={sessions.length} />
          {supporting.length > 0 && <SupportingMetrics series={supporting} />}
        </>
      ) : backing.kind === "segment" ? (
        <SegmentBody sessions={sessions} />
      ) : backing.kind === "activity" ? (
        <p className="focus-tile-note">
          {goal.key === "training_regularity"
            ? regularityText(allSessions)
            : "Wie breit Sie trainieren, zeigt das Raster oben unter „Ihr Training“."}
        </p>
      ) : (
        <GoalMentionBody goal={goal.key} sessions={sessions} note={backing.note} />
      )}

      {/* One drill-down per tile: the goal's own page (which links on to a chart where one exists). Activity
          goals have none — the calendar and variety grid on this screen answer them. */}
      {backing.kind !== "activity" && (
        <Link className="progress-detail-link" to={withPeriod(progressGoalPath(goal.key))}>
          Was dazu gesagt wurde
        </Link>
      )}
    </div>
  );
}

/** How many of a goal's further metrics stand on its tile under the first.
 *  Two: `pace` and `active_listening` name three between them, which together
 *  are the goal, and a third line would turn the tile into the table below. */
const MAX_SUPPORTING = 2;

/**
 * The goal's other metrics, one small line each (`focusMetrics.FOCUS_BACKING`): for rhythm-like goals the
 * combination is the goal. Same terms as the main figure — no band, no value colour.
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
              <span>
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
 * Tile of a goal answered by a comparison rather than a series (ADR 0081): only a count of trainings. The
 * comparison is a table one level down; any single number here would be the composite ADR 0051 refuses.
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
 * A goal with no measurement (`utils/focusMetrics.ts`), answered by counting what the wrap-ups said — a count
 * of statements, not a verdict. No two-mention threshold as in the recurring block: on a tile the user picked,
 * "once so far" is a legitimate answer.
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
  // The newest thing a wrap-up wrote about this goal. `statementsFor` is
  // ordered newest training first and keeps the wrap-up's own order within one,
  // so the first entry is the most recent sentence.
  const latest = statementsFor(sessions, [goal])[0];

  if (total === 0 || (strengths === 0 && improvements === 0)) {
    return <p className="focus-tile-note">{note}</p>;
  }

  // The sentence first, then the tally. For a goal with no measurement the
  // sentences are the whole of what exists, and a count on its own asks the
  // reader to take a number on trust — which is the reading that makes a
  // frequency look like a measurement. Quoted, never summarised, and labelled
  // in words rather than by colour, exactly as the goal's own page does it.
  return (
    <>
      {latest && (
        <figure className="focus-quote">
          <blockquote>{latest.text}</blockquote>
          <figcaption>
            Zuletzt als {latest.kind === "strength" ? "Stärke" : "Verbesserung"} genannt,{" "}
            {formatDate(latest.at) ?? latest.at}
          </figcaption>
        </figure>
      )}

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

  // Selected trainings with no value for this metric, so a course from 6 of 10 does not read as complete.
  // The cause is not claimed: recorded before the metric existed (ADR 0048) or too noisy (ADR 0085).
  const missing = Math.max(0, sessionCount - series.points.length);

  return (
    <>
      <p className="progress-metric-figure">
        {last ? formatPoint(series, last.value) : ""}
        <span className="progress-metric-figure-label"> zuletzt</span>
      </p>
      <Sparkline series={series} />
      <p className="focus-tile-note">
        Ihr üblicher Bereich {formatBand(series) ?? "–"}, aus {series.points.length} Trainings.
        {missing > 0 &&
          ` In ${missing === 1 ? "einem weiteren Training" : `${missing} weiteren Trainings`}` +
            " liegt dazu kein Wert vor."}
      </p>
    </>
  );
}

// --- Replacement when no goals are picked (block B') -------------------------

/** How many series stand in for the focus goals. */
const OVERVIEW_COUNT = 3;

/**
 * Stands in for the focus goals when none are set: the three metrics that moved most, beside an offer to pick
 * goals. Choosing goals is voluntary (F-62), so no content is withheld until you do.
 */
function OverviewSection({ series }: { series: MetricSeries[] }) {
  const { withPeriod } = useProgressContext();
  const withSpread = mostVarying(series, OVERVIEW_COUNT);

  return (
    <section className="progress-section" aria-labelledby="overview-title">
      <SectionHeading id="overview-title" eyebrow="WAS SICH BEWEGT" title="Überblick" />

      {withSpread.length > 0 ? (
        <ul className="focus-tiles">
          {withSpread.map((s) => (
            <li key={s.key}>
              <div className="focus-tile">
                <h3 className="focus-tile-title">{s.name}</h3>
                <MetricBody series={s} sessionCount={s.points.length} />
                <Link className="progress-detail-link" to={withPeriod(progressMetricPath(s.key))}>
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
      <div className="card progress-empty">
        <h2>Noch kein Training abgeschlossen</h2>
        <p className="card-lead">
          Sobald Sie ein Gespräch zu Ende geführt haben, stehen hier Ihre Kennzahlen und ihr
          Verlauf über die Zeit. Ein Verlauf wird ab {MIN_SESSIONS_FOR_SERIES} Trainings
          gezeigt, vorher wären es einzelne Punkte ohne Aussage.
        </p>
        <Link to={ROUTES.training} className="consent-button consent-button-primary">
          Training starten
        </Link>
      </div>

      {goals.length > 0 && (
        <section className="progress-section" aria-labelledby="focus-title">
          <SectionHeading id="focus-title" eyebrow="WORAN SIE ARBEITEN" title="Ihre Fokusziele" />
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
