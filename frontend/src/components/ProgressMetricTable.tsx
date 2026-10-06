import type { CSSProperties } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useProgressContext } from "../ProgressContext";
import { progressMetricPath } from "../routes";
import { GROUPS, groupOf, type MetricGroup } from "../utils/metricGroups";
import {
  MIN_SESSIONS_FOR_SERIES,
  formatBand,
  formatPoint,
  partsSummary,
  type MetricSeries,
} from "../utils/progressStats";
import InfoDetails from "./InfoDetails";
import PartsStrip from "./PartsStrip";
import SectionHeading from "./SectionHeading";
import Sparkline from "./Sparkline";

/** Block C: every metric over time, one sparkline row each, grouped by family.
 * Colour is identity, never a value (`utils/metricGroups`). */
export default function ProgressMetricTable({ series }: { series: MetricSeries[] }) {
  if (series.length === 0) {
    return (
      <section className="progress-section" aria-labelledby="metric-table-title">
        <SectionHeading
          id="metric-table-title"
          title="Kennzahlen über die Zeit"
        />
        <div className="card">
          <p>
            Zu den Trainings in diesem Zeitraum liegen keine Kennzahlen vor. Das kommt vor,
            wenn ein Gespräch sehr kurz war oder die Messung nicht durchlief.
          </p>
        </div>
      </section>
    );
  }

  // Delivery first, as on the post-call screen; inventory order within.
  const groups: MetricGroup[] = ["speech", "content"];

  return (
    <section className="progress-section" aria-labelledby="metric-table-title">
      <SectionHeading
        id="metric-table-title"
        title="Kennzahlen über die Zeit"
      />

      <div className="card metric-table-card">
        {/* Scrolls inside itself: five columns do not reflow. */}
        <div className="metric-table-scroll">
          <table className="metric-table">
            <thead>
              <tr>
                <th scope="col">Kennzahl</th>
                <th scope="col" className="metric-table-num">
                  Zuletzt
                </th>
                <th scope="col" className="metric-table-course">
                  Verlauf
                </th>
                <th scope="col">Ihr üblicher Bereich</th>
                <th scope="col" className="metric-table-num">
                  Trainings
                </th>
              </tr>
            </thead>

            {groups.map((group) => {
              const rows = series.filter((s) => groupOf(s.aspect) === group);
              if (rows.length === 0) return null;
              return (
                <tbody key={group}>
                  <tr className="metric-table-group">
                    <th scope="rowgroup" colSpan={5}>
                      <span
                        className="progress-group-dot"
                        style={{ "--series": GROUPS[group].color } as CSSProperties}
                        aria-hidden="true"
                      />
                      {GROUPS[group].label}
                    </th>
                  </tr>
                  {rows.map((s) => (
                    <MetricRow key={s.key} series={s} />
                  ))}
                </tbody>
              );
            })}
          </table>
        </div>
      </div>

      {/* In view, since "usual range" alone could pass for a target. */}
      <p className="muted progress-note">
        Der übliche Bereich ist aus Ihren eigenen Trainings gerechnet und ist kein Ziel.
      </p>
      <InfoDetails label="Wie diese Tabelle zu lesen ist">
        <p>
          Der übliche Bereich ist der Median Ihrer Werte, erweitert um ihre typische
          Abweichung. Er beschreibt, wo Ihre Werte meistens liegen. Ein Wert außerhalb ist
          weder besser noch schlechter, nur seltener.
        </p>
        <p>
          Zählwerte wie Fragen, Füllwörter oder Unterbrechungen stehen als Anzahl je
          Gespräch. Ein längeres Gespräch hat dabei mehr Gelegenheit dazu; die Gesprächsdauer
          steht deshalb als eigene Zeile in der Tabelle.
        </p>
        <p>
          Ein Verlauf erscheint ab {MIN_SESSIONS_FOR_SERIES} Trainings. Beim Gesprächseinstieg
          steht statt einer Kurve je Training die Zahl der erkannten Teile, weil eine Kurve
          dort wie eine Note gelesen würde. Die Farbe steht für die Gruppe, nie für einen Wert.
        </p>
        <p>
          Die Spalte „Trainings“ sagt, aus wie vielen Gesprächen eine Zeile besteht. Diese
          Zahl kann kleiner sein als die Zahl Ihrer Trainings, wenn eine Aufnahme so viel
          Hintergrundgeräusch hatte, dass sich Sprechen und Stille nicht trennen ließen. Dann
          fehlen Sprechtempo, Sprechpausen, Redefluss, Sprechlänge und Lautstärke für dieses
          eine Gespräch, weil ein Wert daraus mehr über den Raum sagen würde als über Sie.
        </p>
        <p>
          Die Lautstärke fehlt hier mit Absicht. Gemessen wird der Pegel der Aufnahme, und der
          hängt von Mikrofon und Abstand genauso ab wie von Ihnen. Über mehrere Gespräche
          hinweg ist er deshalb nicht vergleichbar. Ihren Verlauf innerhalb eines Gesprächs
          zeigt die Auswertung des jeweiligen Trainings.
        </p>
      </InfoDetails>
    </section>
  );
}

/** The name is the row's real control; the rest takes a click as a mouse convenience. */
function MetricRow({ series }: { series: MetricSeries }) {
  const navigate = useNavigate();
  // The selection travels with the link.
  const { withPeriod } = useProgressContext();
  const path = withPeriod(progressMetricPath(series.key));
  const last = series.points[series.points.length - 1];
  const enough = series.points.length >= MIN_SESSIONS_FOR_SERIES;

  return (
    <tr
      className="metric-table-row"
      onClick={(event) => {
        if ((event.target as HTMLElement).closest("a")) return;
        navigate(path);
      }}
    >
      <th scope="row" className="metric-table-name">
        <Link to={path}>{series.name}</Link>
      </th>

      <td className="metric-table-num metric-table-last">
        {last ? formatPoint(series, last.value) : "–"}
      </td>

      <td className="metric-table-course">
        {series.shape === "parts" ? (
          <PartsStrip series={series} />
        ) : enough ? (
          <Sparkline series={series} height={36} interactive={false} />
        ) : (
          <span className="metric-table-wait">
            Verlauf ab {MIN_SESSIONS_FOR_SERIES} Trainings
          </span>
        )}
      </td>

      <td className="metric-table-band">{bandText(series)}</td>

      <td className="metric-table-num">{series.points.length}</td>
    </tr>
  );
}

/** A dash rather than a range over two values. */
function bandText(series: MetricSeries): string {
  if (series.shape === "parts") return partsSummary(series) ?? "–";
  return formatBand(series) ?? "–";
}
