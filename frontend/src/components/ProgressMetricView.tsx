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
  toSeries,
} from "../utils/progressStats";
import { formatDate } from "../utils/time";
import AppLayout from "./AppLayout";
import EarlyAndLate from "./EarlyAndLate";
import GoalStatements from "./GoalStatements";
import PartsStrip, { partsSummary } from "./PartsStrip";
import Sparkline from "./Sparkline";

/**
 * One metric across the trainings, the dashboard's second level
 * (docs/dashboard-konzept.md, section 7).
 *
 * The table is not a fallback for the chart, it is the other half of it. Which
 * Scenario and which Persona a value came from is what makes it readable at
 * all: a talk share of 62 % in a support call and one in a price negotiation
 * are not the same observation, and the chart cannot say which is which. It is
 * also the accessible alternative, so nothing here exists only as a drawing.
 *
 * Every row links into the training it came from. That is the third and last
 * level, and it is the screen that already exists (`PastSessionView`).
 *
 * Under the table stands what the wrap-ups wrote about the focus goals this
 * metric is evidence for, quoted. Section 7 of the concept asks for it, and
 * it is the half a chart cannot carry: a figure says what happened, the
 * sentence says what it was like.
 */
export default function ProgressMetricView() {
  const { metricKey } = useParams<{ metricKey: string }>();
  // The trainings the switch on the overview selected, not everything stored:
  // this page and the tile that links here have to describe the same set, or
  // the tile's "aus 5 Trainings" and the chart below disagree about what they
  // are about (dashboard-konzept.md section 7, ProgressContext.tsx).
  const { selected: sessions, periodPhrase, state, withPeriod } = useProgressContext();
  const series = toSeries(sessions).find((s) => s.key === metricKey);

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
  // What the wrap-ups wrote about the goals this metric stands behind. The
  // sessions arrive newest first, so the quotations are already in the order
  // the table is in.
  const statements = statementsFor(sessions, goalsForMetric(series.key));

  return (
    <AppLayout pageClassName="app-page-narrow progress-page">
      {back}
      <h1>{series.name}</h1>
      <p className="page-lead">
        {series.points.length} {series.points.length === 1 ? "Training" : "Trainings"}
        {/* A checklist's unit is a bare denominator, which reads as nothing in
            this sentence; its strip below says what the numbers count. */}
        {/* Nor for a count, whose unit is the bare word "count". */}
        {series.unit && series.shape === "line" && !isCount(series.unit) && (
          <>, gemessen in {series.unit}</>
        )}
        . Ohne
        Zielwert, denn für diese Nutzergruppe gibt es keinen belegten Richtwert.
        {series.derivation && <> {series.derivation}</>}
      </p>
      {/* Which trainings this page is drawn over. It carries no switch of its
          own -- the selection is made on the overview and travels in the URL --
          so it has to say in words what it is reading, or a page over the last
          five trainings looks like a page over all of them. */}
      <p className="muted">Gelesen über {periodPhrase}.</p>

      {series.shape === "parts" ? (
        // No line and no band for a checklist (see `SeriesShape`): the count per
        // training, and how often every part was there.
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

      {/* Under the chart and above the table: it is a reading of the same
          curve, and the table is the individual points the two of them
          summarise. */}
      <EarlyAndLate series={series} />

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
                <td className="progress-table-value">{formatPoint(series, point.value)}</td>
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

      <GoalStatements statements={statements} />
    </AppLayout>
  );
}
