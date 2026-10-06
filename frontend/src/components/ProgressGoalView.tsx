import { Link, useParams } from "react-router-dom";

import { useFocusContext } from "../FocusContext";
import { useProgressContext } from "../ProgressContext";
import type { SessionSummary } from "../protocol";
import { ROUTES, progressMetricPath, sessionPath } from "../routes";
import { backingOf } from "../utils/focusMetrics";
import { mentionsFor, statementsFor } from "../utils/goalMentions";
import { segmentTrainings } from "../utils/segmentStats";
import { formatDate } from "../utils/time";
import AppLayout from "./AppLayout";
import GoalStatements from "./GoalStatements";
import SegmentComparison from "./SegmentComparison";

/** One focus goal across trainings: how often named out of how many, every
 * sentence quoted. No verdict (ADR 0080). */
export default function ProgressGoalView() {
  const { goalKey } = useParams<{ goalKey: string }>();
  // The overview's selection, so tile and page count the same trainings.
  const { selected: sessions, series: all, periodPhrase, state, withPeriod } =
    useProgressContext();
  const { focus } = useFocusContext();

  const goal = focus?.goals.find((entry) => entry.key === goalKey);

  const back = (
    <Link to={withPeriod(ROUTES.progress)} className="back-link">
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

  // Null is a failed load: `FocusProvider` waits for its request.
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

  // Retired, or a hand-typed URL.
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
  // Only series with points: an empty metric page promises a missing chart.
  const measured = all.filter((series) =>
    backing.metrics.includes(series.key),
  );

  return (
    <AppLayout pageClassName="app-page-narrow progress-page">
      {back}
      <h1>{goal.title}</h1>
      <p className="page-lead">{goal.caption}</p>
      <p className="muted">Gelesen über {periodPhrase}.</p>

      <div className="card">
        {/* Habit goals are never tagged (ADR 0080), so a zero would be an artefact. */}
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
                <Link to={withPeriod(progressMetricPath(series.key))}>{series.name}</Link>
              </span>
            ))}
            .
          </p>
        )}

        {/* Measured, just not per call: "keine Messung" would be wrong. */}
        {backing.kind === "activity" && (
          <p className="muted">
            Dieses Ziel betrifft Ihr Training selbst, nicht ein einzelnes Gespräch. Wie
            regelmäßig und wie breit Sie trainieren, steht oben auf der{" "}
            <Link to={withPeriod(ROUTES.progress)}>Fortschrittsseite</Link>.
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

/** One block per training (ADR 0081), never aggregated: an average is the number this goal must not have. */
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
