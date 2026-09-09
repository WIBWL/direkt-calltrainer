import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { useFocusContext } from "../FocusContext";
import { useProgressData } from "../hooks/useProgressData";
import type { FocusGoal } from "../protocol";
import { ROUTES, progressMetricPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import {
  MIN_SESSIONS_FOR_SERIES,
  activity,
  activityBuckets,
  durationSeries,
  formatValue,
  variety,
  withinPeriod,
  toSeries,
  type MetricSeries,
} from "../utils/progressStats";
import { formatDate } from "../utils/time";
import ActivityChart from "./ActivityChart";
import AppLayout from "./AppLayout";
import ProgressPreview from "./ProgressPreview";
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
 * (the focus goals), how am I going (the Kennzahlen over time), what next (the
 * practice suggestion). The third block is a preview for now, see
 * `ProgressPreview`.
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
        <p className="progress-activity">
          <strong>{counts.sessions}</strong>
          {counts.sessions === 1 ? " Training" : " Trainings"}
          {counts.sessions > 0 && (
            <>
              , {counts.scenarios} {counts.scenarios === 1 ? "Szenario" : "Szenarien"},{" "}
              {counts.personas} Gesprächspartner
            </>
          )}
          {counts.firstAt && counts.lastAt && (
            <span className="progress-activity-span">
              {" "}
              ({formatDate(counts.firstAt)} bis {formatDate(counts.lastAt)})
            </span>
          )}
        </p>

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

      {inPeriod.length === 0 ? (
        <div className="card">
          <p>
            In diesem Zeitraum liegt kein Training. Wählen Sie oben einen größeren Zeitraum.
          </p>
        </div>
      ) : (
        <>
          {/* Activity first, because it is the one thing that says something
              from the very first training onwards, while the Kennzahlen need a
              handful of calls before they carry anything. */}
          <section className="progress-section">
            <div className="progress-columns">
              <div className="card progress-activity-card">
                <h2>Ihre Trainings im Zeitverlauf</h2>
                <ActivityChart buckets={activityBuckets(inPeriod, days)} />
              </div>

              <div className="card progress-variety-card">
                <h2>Womit Sie trainiert haben</h2>
                <VarietyGrid variety={variety(inPeriod)} />
                <p className="focus-tile-note">
                  Wie oft Sie welches Szenario mit welchem Gesprächspartner gespielt haben.
                </p>
              </div>
            </div>
          </section>

          {goals.length > 0 ? (
            <FocusSection goals={goals} series={series} sessionCount={inPeriod.length} />
          ) : (
            <OverviewSection series={series} />
          )}

          <MetricSection series={series} sessionCount={inPeriod.length} />

          <ProgressPreview />
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
}: {
  goals: FocusGoal[];
  series: MetricSeries[];
  sessionCount: number;
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
            <FocusTile goal={goal} series={series} sessionCount={sessionCount} />
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
}: {
  goal: FocusGoal;
  series: MetricSeries[];
  sessionCount: number;
}) {
  const backing = backingOf(goal.key);
  const primary = series.find((s) => s.key === backing.metrics[0]);

  return (
    <div className="focus-tile">
      <h3 className="focus-tile-title">{goal.title}</h3>

      {backing.kind === "metric" && primary ? (
        <MetricBody series={primary} sessionCount={sessionCount} />
      ) : backing.kind === "activity" ? (
        <p className="focus-tile-note">
          {goal.key === "training_regularity"
            ? `${sessionCount} ${sessionCount === 1 ? "Training" : "Trainings"} im gewählten Zeitraum.`
            : "Wie breit Sie trainieren, sehen Sie an den Szenarien und Gesprächspartnern oben."}
        </p>
      ) : (
        <p className="focus-tile-note">{backing.note}</p>
      )}

      {backing.kind === "metric" && primary && (
        <Link className="progress-detail-link" to={progressMetricPath(primary.key)}>
          Einzelne Trainings ansehen
        </Link>
      )}
    </div>
  );
}

/** A metric's current state: the last value, its course, and the user's own
 *  usual range in words. Shared by the focus tiles and the metric grid. */
function MetricBody({ series, sessionCount }: { series: MetricSeries; sessionCount: number }) {
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
      <Sparkline series={series} />
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
 * goals is voluntary (F-61) and a screen that withholds content until you do
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

function MetricSection({
  series,
  sessionCount,
}: {
  series: MetricSeries[];
  sessionCount: number;
}) {
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

  return (
    <section className="progress-section">
      <h2>Kennzahlen über die Zeit</h2>

      {/* Small multiples: same size, same shape, so the eye compares them
          instead of reading each one on its own terms. */}
      <ul className="progress-metric-grid">
        {series.map((s) => (
          <li key={s.key}>
            <Link className="progress-metric-cell" to={progressMetricPath(s.key)}>
              <span className="progress-metric-cell-name">{s.name}</span>
              <MetricBody series={s} sessionCount={sessionCount} />
            </Link>
          </li>
        ))}
      </ul>
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
