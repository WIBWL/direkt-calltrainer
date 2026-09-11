import type { CSSProperties } from "react";
import { Link, useNavigate } from "react-router-dom";

import { progressMetricPath } from "../routes";
import { GROUPS, groupOf, type MetricGroup } from "../utils/metricGroups";
import {
  MIN_SESSIONS_FOR_SERIES,
  formatBand,
  formatPoint,
  type MetricSeries,
} from "../utils/progressStats";
import InfoDetails from "./InfoDetails";
import PartsStrip, { partsSummary } from "./PartsStrip";
import Sparkline from "./Sparkline";

/**
 * Every Kennzahl over time, one row each (block C of the dashboard).
 *
 * A table and not a grid of tiles, because the tiles stopped working the moment
 * the inventory grew. The concept sized the grid for nine Kennzahlen and put a
 * switch over it so five or six showed at a time; there are sixteen now, the
 * switch showed nine and seven, and the wall it was built against was back. A
 * row per Kennzahl fits all of them on one screen at the app's full width,
 * every sparkline the same size and on the same axis position, which is what
 * lets the eye compare them (Tufte's sparkline table). The switch goes with it:
 * nothing is hidden any more, so there is nothing to switch to.
 *
 * The two families stay, as row groups with a heading in their hue rather than
 * as two halves behind a control. Colour is still identity and never a value
 * (`utils/metricGroups`): the hue hangs off the group, and the table cells never
 * see one.
 *
 * It is also the better accessible form. A screen reader moves through a real
 * table by row and column and hears which Kennzahl a figure belongs to; sixteen
 * links each wrapping a drawing gave it sixteen images with a number in the
 * name.
 */
export default function ProgressMetricTable({ series }: { series: MetricSeries[] }) {
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

  // Sprechweise first, as the post-call screen opens on it: the reading the
  // transcript cannot give. Within a group the order is the backend's own
  // inventory order, which is the order the series arrive in.
  const groups: MetricGroup[] = ["speech", "content"];

  return (
    <section className="progress-section" aria-labelledby="metric-table-title">
      <div className="progress-section-head">
        <h2 id="metric-table-title">Kennzahlen über die Zeit</h2>
      </div>

      <div className="card metric-table-card">
        {/* Scrolls inside itself on a narrow screen rather than pushing the
            page sideways: five columns do not reflow into anything readable. */}
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

      {/* The one sentence that must be read with the column headed "Ihr
          üblicher Bereich" stays in view, since that heading alone could pass
          for a target. The rest is how the table was made. */}
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
          Die Lautstärke fehlt hier mit Absicht. Gemessen wird der Pegel der Aufnahme, und der
          hängt von Mikrofon und Abstand genauso ab wie von Ihnen. Über mehrere Gespräche
          hinweg ist er deshalb nicht vergleichbar. Ihren Verlauf innerhalb eines Gesprächs
          zeigt die Auswertung des jeweiligen Trainings.
        </p>
      </InfoDetails>
    </section>
  );
}

/**
 * One Kennzahl.
 *
 * The name is the link, so the row has one real control for the keyboard and
 * the screen reader. The rest of the row takes a click too, as a convenience
 * for the mouse: a thin name is a small target on a row this wide, and the row
 * already highlights as one thing under the pointer.
 */
function MetricRow({ series }: { series: MetricSeries }) {
  const navigate = useNavigate();
  const path = progressMetricPath(series.key);
  const last = series.points[series.points.length - 1];
  const enough = series.points.length >= MIN_SESSIONS_FOR_SERIES;

  return (
    <tr
      className="metric-table-row"
      onClick={(event) => {
        // The link handles its own click; everything else in the row forwards.
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

/** The fourth column: the user's own usual range, or for a checklist how often
 *  it was complete. A dash where neither can be said yet, rather than a range
 *  over two values that describes nothing. */
function bandText(series: MetricSeries): string {
  if (series.shape === "parts") return partsSummary(series) ?? "–";
  return formatBand(series) ?? "–";
}
