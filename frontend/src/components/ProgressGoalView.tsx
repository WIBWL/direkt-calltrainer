import { Link, useParams } from "react-router-dom";

import { useFocusContext } from "../FocusContext";
import { useProgressData } from "../hooks/useProgressData";
import type { SessionSummary } from "../protocol";
import { ROUTES, progressMetricPath, sessionPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import { mentionsFor, statementsFor } from "../utils/goalMentions";
import { toSeries } from "../utils/progressStats";
import { segmentTrainings } from "../utils/segmentStats";
import { formatDate } from "../utils/time";
import AppLayout from "./AppLayout";
import GoalStatements from "./GoalStatements";
import SegmentComparison from "./SegmentComparison";

/**
 * One focus goal across the trainings, the dashboard's second level for the
 * other half of the overview (docs/dashboard-konzept.md, section 7, which puts
 * a metric and a Focus Goal on the same level here).
 *
 * The tiles in block B were a dead end until this existed, and for the goals
 * with no measurement they were the *only* thing on screen about that goal — a
 * bare count with no way to see what was said. A count the reader cannot check
 * is worse than none, because it looks like a measurement.
 *
 * So, in order: what the goal is, how often it was named and out of how many,
 * then every sentence quoted and linking into its call. Where a metric stands
 * behind the goal it links there rather than redrawing the chart — one chart,
 * one page, or the two start disagreeing about what "in this period" means.
 *
 * No verdict anywhere. The wording is ADR 0080's throughout, because this is
 * the page where a frequency is most likely to be read as a grade.
 */
export default function ProgressGoalView() {
  const { goalKey } = useParams<{ goalKey: string }>();
  const { sessions, state } = useProgressData();
  const { focus } = useFocusContext();

  const goal = focus?.goals.find((entry) => entry.key === goalKey);

  const back = (
    <Link to={ROUTES.progress} className="back-link">
      Zurück zum Fortschritt
    </Link>
  );

  if (state === "loading") {
    return (
      <AppLayout pageClassName="app-page-narrow progress-page">
        {back}
        <p className="muted">Wird geladen …</p>
      </AppLayout>
    );
  }

  // The catalogue is what turns the key into a goal, so without it there is
  // nothing to name. Null here is a failed load and not one still running:
  // `FocusProvider` renders nothing below it until its request has settled.
  if (!focus) {
    return (
      <AppLayout pageClassName="app-page-narrow progress-page">
        {back}
        <h1>Fokusziel</h1>
        <div className="card">
          <p>Ihre Fokusziele konnten nicht geladen werden. Bitte laden Sie die Seite neu.</p>
        </div>
      </AppLayout>
    );
  }

  // An unknown key is a goal that was retired, or a hand-typed URL. Both are
  // the same answer: the catalogue has nothing under this name, and there is
  // nothing to show for it.
  if (state === "failed" || !goal || !goalKey) {
    return (
      <AppLayout pageClassName="app-page-narrow progress-page">
        {back}
        <h1>Fokusziel</h1>
        <div className="card">
          <p>Zu diesem Fokusziel liegt nichts vor. Möglicherweise gibt es das Ziel nicht mehr.</p>
        </div>
      </AppLayout>
    );
  }

  const { strengths, improvements, total } = mentionsFor(sessions, goalKey);
  const statements = statementsFor(sessions, [goalKey]);
  const backing = backingOf(goalKey);
  // Only a series that actually has points: linking to an empty metric page
  // promises a chart that is not there.
  const measured = toSeries(sessions).filter((series) =>
    backing.metrics.includes(series.key),
  );

  return (
    <AppLayout pageClassName="app-page-narrow progress-page">
      {back}
      <h1>{goal.title}</h1>
      <p className="page-lead">{goal.caption}</p>

      <div className="card">
        {/* Habit goals are never tagged -- the wrap-up is refused them in the
            prompt and again when the tags are stored (ADR 0080) -- so a count
            of zero would be an artefact and not an observation. */}
        {backing.kind !== "activity" &&
          (total === 0 ? (
            <p>
              Zu diesem Ziel liegt noch keine Auswertung vor. Ausgewertet wird nach jedem
              Gespräch, und erst die Auswertungen sagen etwas zu diesem Ziel.
            </p>
          ) : (
            <p>
              In {improvements} von {total} ausgewerteten Trainings als Verbesserungspunkt
              genannt, in {strengths} als Stärke. Gezählt wird, was Ihre Auswertungen
              geschrieben haben, nicht wie gut ein Gespräch war.
            </p>
          ))}

        {measured.length > 0 && (
          <p>
            Gemessen wird dazu:{" "}
            {measured.map((series, index) => (
              <span key={series.key}>
                {index > 0 && ", "}
                <Link to={progressMetricPath(series.key)}>{series.name}</Link>
              </span>
            ))}
            .
          </p>
        )}

        {/* An activity goal is answered by the figures at the top of the
            overview and by nothing on this page. Saying "keine Messung" here
            would be wrong in the other direction: those goals are measured,
            just not per call. */}
        {backing.kind === "activity" && (
          <p className="muted">
            Dieses Ziel betrifft Ihr Training selbst, nicht ein einzelnes Gespräch. Wie
            regelmäßig und wie breit Sie trainieren, steht oben auf der{" "}
            <Link to={ROUTES.progress}>Fortschrittsseite</Link>.
          </p>
        )}

        {backing.kind === "text" && (
          <p className="muted">
            Zu diesem Ziel gibt es keine Messung. Was dazu gesagt werden kann, steht in den
            Auswertungen Ihrer einzelnen Gespräche.
          </p>
        )}
      </div>

      {backing.kind === "segment" && <PressureSection sessions={sessions} />}

      <GoalStatements statements={statements} />
    </AppLayout>
  );
}

/**
 * The comparison behind "composure under pressure", one block per training
 * (ADR 0081).
 *
 * Per training and not aggregated across them. Averaging the pressure figures
 * of six calls against their calm figures would hide that the pressure in each
 * call was a different thing -- a price objection in one, a complaint in
 * another -- and would produce the single number this goal must not have. The
 * trainings are listed newest first and each links into itself.
 */
function PressureSection({ sessions }: { sessions: SessionSummary[] }) {
  const trainings = segmentTrainings(sessions);

  if (trainings.length === 0) {
    return (
      <>
        <h2>Unter Druck und sonst</h2>
        <div className="card">
          <p>
            Für dieses Ziel wird verglichen, wie Sie an den fordernden Stellen eines
            Gesprächs gesprochen haben und wie im Rest. Dafür muss es solche Stellen geben:
            Ihr Gegenüber muss widersprochen, nachgehakt oder etwas verlangt haben, und
            beide Teile müssen lang genug sein, um gemessen zu werden.
          </p>
          <p className="muted">
            Für Trainings von vor dieser Auswertung gibt es den Vergleich nicht und wird es
            ihn nicht geben: Die Aufnahme wird nach dem Gespräch gelöscht, und was damals
            nicht mitgemessen wurde, lässt sich nicht nachholen.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <h2>Unter Druck und sonst</h2>
      {trainings.map((training) => (
        <div className="card" key={training.sessionId}>
          <p className="segment-training">
            <Link to={sessionPath(training.sessionId)}>
              {training.scenario} am {formatDate(training.at) ?? training.at}
            </Link>{" "}
            <span className="muted">· Gespräch mit {training.persona}</span>
          </p>
          <SegmentComparison pairs={training.pairs} caveat={false} />
        </div>
      ))}
      <p className="muted">
        Als fordernd gelten die Stellen, an denen Ihr Gegenüber widersprochen, nachgehakt
        oder etwas verlangt hat. Welche das waren, hat das Sprachmodell beim Schreiben der
        Auswertung bestimmt; die Zahlen daneben sind gemessen. Ein Unterschied zwischen den
        Spalten ist eine Beobachtung und keine Bewertung: Es gibt keinen belegten Wert
        dafür, wie groß er sein darf. Verglichen wird immer innerhalb eines Gesprächs, weil
        der Druck in jedem Gespräch ein anderer war.
      </p>
    </>
  );
}
