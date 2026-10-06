import { Link, useParams } from "react-router-dom";

import { useProgressContext } from "../ProgressContext";
import { ROUTES, sessionPath } from "../routes";
import { goalsForMetric } from "../utils/focusMetrics";
import { statementsFor } from "../utils/goalMentions";
import { isCount } from "../utils/metrics";
import {
  MIN_SESSIONS_FOR_SERIES,
  formatPoint,
  formatBand,
  partsSummary,
} from "../utils/progressStats";
import { formatDate } from "../utils/time";
import AppLayout from "./AppLayout";
import EarlyAndLate from "./EarlyAndLate";
import GoalStatements from "./GoalStatements";
import PartsStrip from "./PartsStrip";
import Sparkline from "./Sparkline";

/** One metric across trainings. The table is the chart's accessible half; rows
 * link to the training, and the backed goals' statements follow. */
export default function ProgressMetricView() {
  const { metricKey } = useParams<{ metricKey: string }>();
  // The overview's selection, so the tile and this page describe the same set.
  const { selected: sessions, series: all, periodPhrase, state, withPeriod } =
    useProgressContext();
  const series = all.find((s) => s.key === metricKey);

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

  if (state === "failed" || !series) {
    return (
      <AppLayout pageClassName="app-page-narrow progress-page">
        {back}
        <h1>Kennzahl</h1>
        <div className="card">
          {/* The usual reason is the selection, not the metric. */}
          <p>
            Über {periodPhrase} liegt zu dieser Kennzahl kein Wert vor. Mit einer weiteren
            Auswahl auf der Fortschrittsseite steht hier unter Umständen mehr; sonst wurde sie
            in Ihren Trainings noch nicht gemessen.
          </p>
        </div>
      </AppLayout>
    );
  }

  // Newest first in the table, oldest first in the chart.
  const rows = [...series.points].reverse();
  const statements = statementsFor(sessions, goalsForMetric(series.key));

  return (
    <AppLayout pageClassName="app-page-narrow progress-page">
      {back}
      <h1>{series.name}</h1>
      <p className="page-lead">
        {series.points.length} {series.points.length === 1 ? "Training" : "Trainings"}
        {/* Not for a checklist's bare denominator or the word "count". */}
        {series.unit && series.shape === "line" && !isCount(series.unit) && (
          <>, gemessen in {series.unit}</>
        )}
        . Ohne
        Zielwert, denn für diese Nutzergruppe gibt es keinen belegten Richtwert.
        {series.derivation && <> {series.derivation}</>}
      </p>
      {/* No switch here, so it says what it reads. */}
      <p className="muted">Gelesen über {periodPhrase}.</p>

      {series.shape === "parts" ? (
        // A checklist has no line or band.
        <div className="card">
          <PartsStrip series={series} />
          <p className="muted">
            {partsSummary(series) ?? "Je Training, wie viele Teile erkannt wurden"}. Die Zahl
            in jedem Feld ist ein Training, das älteste links. Welche Teile es waren, steht in
            der Auswertung des Trainings selbst.
          </p>
        </div>
      ) : series.points.length >= MIN_SESSIONS_FOR_SERIES ? (
        <div className="card">
          <Sparkline series={series} width={640} height={160} />
          {series.band && (
            <p className="muted">
              Das Band ist der Bereich, in dem Ihre Werte meistens liegen: {formatBand(series)}.
              Es ist aus Ihren eigenen Werten gerechnet und kein Zielbereich.
            </p>
          )}
        </div>
      ) : (
        <div className="card">
          <p>
            Für einen Verlauf sind es noch zu wenige Trainings. Ab {MIN_SESSIONS_FOR_SERIES}{" "}
            gemessenen Gesprächen wird hier eine Kurve gezeigt.
          </p>
        </div>
      )}

      <EarlyAndLate series={series} />

      <h2>Einzelne Trainings</h2>
      <div className="card">
        <div className="progress-table-scroll">
          <table className="progress-table">
            <thead>
              <tr>
                <th scope="col">Datum</th>
                <th scope="col">Szenario</th>
                <th scope="col">Gesprächspartner</th>
                <th scope="col" className="progress-table-value">
                  Wert
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((point) => (
                <tr key={point.sessionId}>
                  <td>
                    <Link to={sessionPath(point.sessionId)}>
                      {formatDate(point.at) ?? point.at}
                    </Link>
                  </td>
                  <td>{point.scenario}</td>
                  <td>{point.persona}</td>
                  <td className="progress-table-value">{formatPoint(series, point.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="muted">
        Szenario und Gesprächspartner stehen dabei, weil sie den Wert beeinflussen. Ein
        Redeanteil in einer Preisverhandlung und einer in einem kurzen Servicefall sind nicht
        dieselbe Beobachtung.
      </p>

      <GoalStatements statements={statements} />
    </AppLayout>
  );
}
