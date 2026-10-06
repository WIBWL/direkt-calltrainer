import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { useFocusContext } from "../FocusContext";
import { OCCASIONS, PERIODS, useProgressContext } from "../ProgressContext";
import type { FocusGoal, SessionSummary } from "../protocol";
import { ROUTES, progressGoalPath, progressMetricPath } from "../routes";
import { showsInOverview } from "../utils/metrics";
import {
  focusOutline,
  metricReading,
  type FocusOutline,
  type FocusReading,
} from "../utils/progressOutline";
import { downloadProgressPdf } from "../utils/progressPdf";
import {
  MIN_SESSIONS_FOR_SERIES,
  mostVarying,
  activity,
  formatPoint,
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

/** Progress dashboard (F-13): activity over everything, then the period switch,
 * then goals, recurring themes and metrics over the selection. Nothing evaluated (ADR 0065). */
export default function ProgressView() {
  // From the provider, so a tile and the page behind it read the same set.
  const {
    sessions,
    selected: inPeriod,
    readable,
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
  // Over everything stored, like the calendar beside it.
  const counts = activity(sessions);
  const goals = pickedGoals(focus?.goals ?? [], focus?.selected ?? []);
  // Decided once for this screen and the report (ADR 0102).
  const outline = focusOutline({
    goals,
    series,
    selected: inPeriod,
    readable,
    shows: showsInOverview,
  });
  // Left out of the courses only; said, or they would be overstated.
  const tooShort = inPeriod.length - readable.length;

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

  // The reason is a setting, not a lack of training.
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

      <section className="progress-section progress-training-section" aria-labelledby="activity-title">
        <SectionHeading id="activity-title" title="Ihr Training" />

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

      {/* Everything above counts every training; everything below the selection. */}
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

        {/* A course across kinds of call is scatter; an empty option cannot be pressed. */}
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
          {tooShort > 0 && (
            <>
              {". "}
              {tooShort === 1
                ? "Ein Gespräch davon war zu kurz"
                : `${tooShort} Gespräche davon waren zu kurz`}
              , um daraus Kennzahlen zu lesen. Gezählt {tooShort === 1 ? "ist es" : "sind sie"}{" "}
              oben mit.
            </>
          )}
        </span>
      </div>

      {/* Empty only through the occasion row, e.g. from a shared link. */}
      {inPeriod.length === 0 ? (
        <div className="card">
          <p>
            Zu diesem Gesprächsanlass liegt in Ihrer Auswahl kein Training vor. Mit „Alle
            Anlässe“ steht hier wieder alles.
          </p>
        </div>
      ) : (
        <>
          {outline.length > 0 ? (
            <FocusSection outline={outline} allSessions={sessions} />
          ) : (
            <OverviewSection series={overview} />
          )}

          <ProgressRecurring
            sessions={inPeriod}
            catalogue={focus?.goals ?? []}
            practice={<ProgressPractice sessions={inPeriod} catalogue={focus?.goals ?? []} />}
          />

          <ProgressMetricTable series={overview} />
        </>
      )}

      <DownloadReport />
    </Frame>
  );
}

/** The screen as a PDF (F-13), built from the page's own numbers. */
function DownloadReport() {
  const { sessions, selected, periodPhrase, truncated } = useProgressContext();
  const { focus } = useFocusContext();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

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

function Frame({ children }: { children: ReactNode }) {
  return (
    <AppLayout progressActive pageClassName="app-page-wide progress-page">
      <h1>Ihr Fortschritt</h1>
      {/* That nothing is graded is said up front: an untold reader assumes higher is better. */}
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

/** Catalogue order; a retired goal drops out. */
function pickedGoals(catalogue: FocusGoal[], selected: string[]): FocusGoal[] {
  return catalogue.filter((goal) => selected.includes(goal.key));
}

function FocusSection({
  outline,
  allSessions,
}: {
  /** Decided in `utils/progressOutline.ts`; the report renders the same list. */
  outline: FocusOutline[];
  /** Everything stored, whatever the switch says. */
  allSessions: SessionSummary[];
}) {
  return (
    <section className="progress-section" aria-labelledby="focus-title">
      <SectionHeading
        id="focus-title"
        title="Ihre Fokusziele"
        aside={
          <Link to={ROUTES.profile} className="progress-section-link">
            Ziele ändern
          </Link>
        }
      />

      <ul className="focus-tiles">
        {outline.map((entry) => (
          <li key={entry.key}>
            <FocusTile entry={entry} allSessions={allSessions} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** One focus goal in the shape `utils/progressOutline.ts` decided. None is ever
 * hidden, or the user would believe it tracked (ADR 0102). */
function FocusTile({
  entry,
  allSessions,
}: {
  entry: FocusOutline;
  /** For the regularity goal, which is about the calendar, not the selection. */
  allSessions: SessionSummary[];
}) {
  const { withPeriod } = useProgressContext();
  const reading = entry.reading;

  return (
    <div className="focus-tile">
      <h3 className="focus-tile-title">{entry.title}</h3>

      {reading.kind === "metric" ? (
        <>
          <MetricBody reading={reading} />
          {reading.supporting.length > 0 && <SupportingMetrics series={reading.supporting} />}
        </>
      ) : reading.kind === "no-value" ? (
        // Measured, but nothing in this selection carries it.
        <p className="focus-tile-note">{reading.note}</p>
      ) : reading.kind === "segment" ? (
        <SegmentBody trainings={reading.trainings} />
      ) : reading.kind === "activity" ? (
        <p className="focus-tile-note">
          {reading.goal === "training_regularity"
            ? regularityText(allSessions)
            : "Wie breit Sie trainieren, zeigt das Raster oben unter „Ihr Training“."}
        </p>
      ) : (
        <GoalMentionBody reading={reading} />
      )}

      {/* Activity goals have no page: the calendar and variety grid answer them. */}
      {reading.kind !== "activity" && (
        <Link className="progress-detail-link" to={withPeriod(progressGoalPath(entry.key))}>

          Was dazu gesagt wurde
        </Link>
      )}
    </div>
  );
}

/** For rhythm-like goals the combination is the goal. No band, no value colour. */
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

/** A count and a date, no verdict: nobody has established how often is enough. */
function regularityText(sessions: SessionSummary[]): string {
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const completed = sessions.filter((s) => s.status === "completed");
  const recent = completed.filter((s) => new Date(s.started_at).getTime() >= cutoff).length;
  const last = completed[0]?.started_at;
  const count = `${recent} ${recent === 1 ? "Training" : "Trainings"} in den letzten 30 Tagen`;
  return last ? `${count}, zuletzt am ${formatDate(last) ?? last}.` : `${count}.`;
}

/** Only a count (ADR 0081): any single number here would be the composite ADR 0051 refuses. */
function SegmentBody({ trainings }: { trainings: number }) {
  const withComparison = trainings;

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

/** Counting what the wrap-ups said: statements, not a verdict. No two-mention
 * threshold here: on a picked goal "once so far" is an answer. */
function GoalMentionBody({
  reading,
}: {
  reading: Extract<FocusReading, { kind: "mentions" }>;
}) {
  const { strengths, improvements, total, latest, note, measured } = reading;

  if (total === 0 || (strengths === 0 && improvements === 0)) {
    return <p className="focus-tile-note">{note}</p>;
  }

  // The sentences first, quoted: a count alone looks like a measurement.
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
        {measured
          ? "Noch kein Messwert in dieser Auswahl. "
          : "Keine Messung. "}
        Gezählt wird, in wie vielen ausgewerteten Trainings es genannt wurde.
      </p>
    </>
  );
}

/** Shared by the focus tiles and the overview, so a metric cannot say two things. */
function MetricBody({ reading }: { reading: Extract<FocusReading, { kind: "metric" }> }) {
  const { series, last, band, trainings, missing } = reading;

  // A checklist has no course and no band.
  if (series.shape === "parts") {
    const summary = partsSummary(series);
    return (
      <>
        <p className="progress-metric-figure">
          {last ?? "noch kein Wert"}
          {last && <span className="progress-metric-figure-label"> zuletzt</span>}
        </p>
        <PartsStrip series={series} />
        {summary && <p className="focus-tile-note">{summary}.</p>}
      </>
    );
  }

  if (trainings < MIN_SESSIONS_FOR_SERIES) {
    return (
      <>
        <p className="progress-metric-figure">{last ?? "noch kein Wert"}</p>
        <p className="focus-tile-note">
          Ab {MIN_SESSIONS_FOR_SERIES} Trainings wird hier der Verlauf gezeigt. Bisher{" "}
          {trainings} von {trainings + missing}.
        </p>
      </>
    );
  }

  return (
    <>
      <p className="progress-metric-figure">
        {last ?? ""}
        <span className="progress-metric-figure-label"> zuletzt</span>
      </p>
      <Sparkline series={series} />
      {/* So a course from 6 of 10 does not read as complete (ADR 0085). */}
      <p className="focus-tile-note">
        Ihr üblicher Bereich {band ?? "–"}, aus {trainings} Trainings.
        {missing > 0 &&
          ` In ${missing === 1 ? "einem weiteren Training" : `${missing} weiteren Trainings`}` +
            " liegt dazu kein Wert vor."}
      </p>
    </>
  );
}

const OVERVIEW_COUNT = 3;

/** The three metrics that moved most, when no goals are picked (F-62). */
function OverviewSection({ series }: { series: MetricSeries[] }) {
  // `readable`, not the series' own points, or the "no value" line never fires.
  const { readable, withPeriod } = useProgressContext();
  const withSpread = mostVarying(series, OVERVIEW_COUNT);

  return (
    <section className="progress-section" aria-labelledby="overview-title">
      <SectionHeading id="overview-title" title="Überblick" />

      {withSpread.length > 0 ? (
        <ul className="focus-tiles">
          {withSpread.map((s) => (
            <li key={s.key}>
              <div className="focus-tile">
                <h3 className="focus-tile-title">{s.name}</h3>
                <MetricBody reading={metricReading(s, readable.length)} />
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
          <SectionHeading id="focus-title" title="Ihre Fokusziele" />
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
