import { Link, useParams } from "react-router-dom";

import { useProgressData } from "../hooks/useProgressData";
import { ROUTES, sessionPath } from "../routes";
import { MIN_SESSIONS_FOR_SERIES, formatValue, toSeries } from "../utils/progressStats";
import { formatDate } from "../utils/time";
import AppLayout from "./AppLayout";
import Sparkline from "./Sparkline";

/**
 * One Kennzahl across the trainings, the dashboard's second level
 * (docs/dashboard-konzept.md, section 7).
 *
 * The table is not a fallback for the chart, it is the other half of it. Which
 * Scenario and which Persona a value came from is what makes it readable at
 * all: a Redeanteil of 62 % in a support call and one in a price negotiation
 * are not the same observation, and the chart cannot say which is which. It is
 * also the accessible alternative, so nothing here exists only as a drawing.
 *
 * Every row links into the training it came from. That is the third and last
 * level, and it is the screen that already exists (`PastSessionView`).
 */
export default function ProgressMetricView() {
  const { metricKey } = useParams<{ metricKey: string }>();
  const { sessions, state } = useProgressData();
  const series = toSeries(sessions).find((s) => s.key === metricKey);

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

  if (state === "failed" || !series) {
    return (
      <AppLayout pageClassName="app-page-narrow progress-page">
        {back}
        <h1>Kennzahl</h1>
        <div className="card">
          <p>
            Zu dieser Kennzahl liegen keine Werte vor. Möglicherweise wurde sie in Ihren
            Trainings noch nie gemessen.
          </p>
        </div>
      </AppLayout>
    );
  }

  // Newest first in the table, oldest first in the chart: a chart reads left to
  // right in time, a list is read from the most recent entry down.
  const rows = [...series.points].reverse();

  return (
    <AppLayout pageClassName="app-page-narrow progress-page">
      {back}
      <h1>{series.name}</h1>
      <p className="page-lead">
        {series.points.length} {series.points.length === 1 ? "Training" : "Trainings"}
        {series.unit && <>, gemessen in {series.unit}</>}. Ohne Zielwert, denn für diese
        Nutzergruppe gibt es keinen belegten Richtwert.
      </p>

      {series.points.length >= MIN_SESSIONS_FOR_SERIES ? (
        <div className="card">
          <Sparkline series={series} width={640} height={160} />
          {series.band && (
            <p className="muted">
              Das Band ist der Bereich, in dem Ihre Werte meistens liegen:{" "}
              {formatValue(series.band.low, null)} bis {formatValue(series.band.high, series.unit)}.
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

      <h2>Einzelne Trainings</h2>
      <div className="card">
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
                <td className="progress-table-value">
                  {formatValue(point.value, series.unit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="muted">
        Szenario und Gesprächspartner stehen dabei, weil sie den Wert beeinflussen. Ein
        Redeanteil in einer Preisverhandlung und einer in einem kurzen Servicefall sind nicht
        dieselbe Beobachtung.
      </p>
    </AppLayout>
  );
}
