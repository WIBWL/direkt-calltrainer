import { type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { useFocusContext } from "../FocusContext";
import { OCCASIONS, PERIODS, useProgressContext } from "../ProgressContext";
import type { FocusGoal, SessionSummary } from "../protocol";
import { ROUTES, progressGoalPath, progressMetricPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import { mentionsFor, statementsFor } from "../utils/goalMentions";
import { showsInOverview } from "../utils/metrics";
import { segmentTrainings } from "../utils/segmentStats";
import {
  MIN_SESSIONS_FOR_SERIES,
  activity,
  durationSeries,
  formatPoint,
  formatBand,
  variety,
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
import SectionHeading from "./SectionHeading";
import Sparkline from "./Sparkline";
import VarietyGrid from "./VarietyGrid";

/**
 * The progress dashboard (F-13, docs/dashboard-konzept.md).
 *
 * Top to bottom: what I did (the counted figures, calendar and variety grid,
 * over every stored training), the period switch, then Hattie & Timperley's
 * feed up, feed forward and feed back — focus goals, what the wrap-ups keep
 * returning to with the one thing to practise beside it, and every metric over
 * time — read over the trainings the switch selects. The block that leads back
 * into training stays high: a dashboard whose only way out is at the foot of
 * its longest page ends in looking (dashboard-konzept.md section 3).
 *
 * The switch sits *under* the activity block deliberately: everything above it
 * counts every stored training, everything below is read over the selection, so
 * placement says what would otherwise need a caveat. What it selects reaches
 * the two detail levels as well, through the URL rather than through state
 * here (`ProgressContext.tsx`): a tile that says "aus 5 Trainings" and a page
 * behind it drawn over every stored one are two screens describing the same
 * metric differently.
 *
 * Nothing here is evaluated — no target band, no colour meaning good, no arrow,
 * no aggregate score (ADR 0065), because nobody has established what a good
 * talk share or speaking pace is for this population. The figures were measured
 * when each call ended (ADR 0051); this view only groups them and describes
 * their spread.
 *
 * Read-only and about one account. No comparison with colleagues, though the
 * tenant model (ADR 0060) would allow it: ranking employees against each other
 * is a different product with a different legal footing.
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
  // The call length rides along with the measured metrics. It is derived
  // from the two timestamps rather than measured from the audio, but it belongs
  // to the same family: descriptive, and in need of no norm to be readable.
  const duration = durationSeries(inPeriod);
  const series = [...toSeries(inPeriod), ...(duration ? [duration] : [])];
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

      {/* First, and above the switch: what was done, over every stored
          training. Activity needs no norm to be readable (ADR 0065 says so
          outright), so it is the one block that can open the page with a figure
          and no caveat. It stood last for a while, as context; at the top it is
          the ground the rest of the page stands on, and it is the part a
          returning User checks first ("when did I last train?"). */}
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

        {/* The second row, and the same control as the first, so the two
            cannot read as different kinds of choice. It answers the objection
            the concept raises against its own charts (section 4.3): a course
            across a complaint, a price negotiation and an advisory call is
            scatter, and across one kind of call it is a series. Each option
            carries how many trainings it would yield, and an occasion with
            none cannot be pressed — a filter leading to an empty page is a
            dead end nobody meant to offer. */}
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
    </Frame>
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
 * One focus goal.
 *
 * Four shapes, because the honest answer differs per goal (see
 * `utils/focusMetrics.ts`): metrics with their course, a comparison of two
 * stretches of a call, an activity figure, or what the wrap-ups said where
 * there is no measurement. The last is deliberately not hidden. A tile that
 * quietly disappears would let the user believe the goal is being tracked.
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

      {/* One drill-down per tile, and it is the goal's own page rather than a
          metric's: a tile stands for a goal, and the goals with no
          measurement need the level most. That page links on to the chart
          where there is one, and the metrics table below still reaches the
          charts in one click. Activity goals have none -- what answers them is
          the calendar and the variety grid on this very screen. */}
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
 * The goal's other metrics, one line each: name, the last value, a small
 * course.
 *
 * The first metric alone told half the story. speaking pace, pauses and
 * run length are together the rhythm of somebody's speaking, and each
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
 * The tile of a goal answered by a comparison rather than by a series
 * (ADR 0081): how somebody spoke while the other side pushed back, against the
 * rest of the call.
 *
 * A count of trainings and nothing else here. The comparison itself is two
 * figures per metric per training, which is a table and not a tile, so it
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
 * Three of the fourteen goals are like this (`utils/focusMetrics.ts`): whether
 * an objection was handled or empathy shown is in what was said, and no
 * acoustic figure reaches it. Counting the mentions is the honest substitute,
 * and the wording keeps it a count of statements rather than a verdict.
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

  // How many of the selected trainings carry no value for this metric. A
  // course drawn from 6 of 10 trainings says "6" beside it and nothing about
  // the other four, which reads as a complete record with a short memory. Two
  // things produce a gap and the sentence claims neither: a call recorded
  // before the metric existed (ADR 0048 — the audio is gone, so it can never
  // be filled in), and one whose recording was too noisy to tell speech from
  // silence, which withholds five metrics at once (ADR 0085).
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

/**
 * What stands where the focus goals would be when none are set.
 *
 * Not an empty box and not a nag. The three metrics that moved most across
 * the period are the ones where there is something to look at, so they earn the
 * space; the invitation to pick goals sits beside them as an offer. Choosing
 * goals is voluntary (F-62) and a screen that withholds content until you do
 * would make it less so.
 */
function OverviewSection({ series }: { series: MetricSeries[] }) {
  const { withPeriod } = useProgressContext();
  const withSpread = series
    .filter((s) => s.points.length >= MIN_SESSIONS_FOR_SERIES && s.band)
    .map((s) => ({
      series: s,
      // Relative spread, so a talk share in percent and a reaction time in
      // seconds can be compared at all.
      spread: s.band ? (s.band.high - s.band.low) / (Math.abs(s.band.median) || 1) : 0,
    }))
    .sort((a, b) => b.spread - a.spread)
    .slice(0, 3);

  return (
    <section className="progress-section" aria-labelledby="overview-title">
      <SectionHeading id="overview-title" eyebrow="WAS SICH BEWEGT" title="Überblick" />

      {withSpread.length > 0 ? (
        <ul className="focus-tiles">
          {withSpread.map(({ series: s }) => (
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
