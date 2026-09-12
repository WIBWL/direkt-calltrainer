import { useState } from "react";

import { colorOf } from "../utils/metricGroups";
import type { MetricSeries } from "../utils/progressStats";
import { formatPoint } from "../utils/progressStats";
import { formatDate } from "../utils/time";

/**
 * One metric over the trainings in the period (F-13,
 * docs/dashboard-konzept.md).
 *
 * The user's own values as a line over their own usual range (median widened by
 * their own spread). No target band, no colour meaning good or bad, no arrow,
 * no regression line: a trend through nine points from nine different Scenarios
 * would assert a direction the data cannot carry, which ADR 0065 rules out for
 * this view.
 *
 * Colour is the metric's family and never its value (`utils/metricGroups`),
 * which is the whole of what makes colour admissible here.
 *
 * Inline SVG, like LoudnessCourse: a band, a line and a few dots do not warrant
 * shipping a charting library.
 *
 * The accessible name carries the numbers, and the hover adds to that rather
 * than replacing it — the detail view repeats every point as a real table.
 */
export default function Sparkline({
  series,
  width = 240,
  height = 56,
  showDots = true,
  interactive = true,
}: {
  series: MetricSeries;
  width?: number;
  height?: number;
  showDots?: boolean;
  /** Off inside a link, where a nested interactive layer would fight the
   *  link's own hit area for the pointer. */
  interactive?: boolean;
}) {
  const [active, setActive] = useState<number | null>(null);
  const values = series.points.map((p) => p.value);
  if (values.length === 0) return null;

  const lowest = Math.min(...values, series.band?.low ?? Infinity);
  const highest = Math.max(...values, series.band?.high ?? -Infinity);
  // A flat series would divide by zero; giving it a nominal span puts the line
  // in the middle of the box instead, which is what a flat series looks like.
  const span = highest - lowest || Math.abs(highest) || 1;
  const pad = 6;
  const plot = height - pad * 2;
  const color = colorOf(series.aspect);

  const x = (index: number) =>
    values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
  const y = (value: number) => pad + plot - ((value - lowest) / span) * plot;

  const line = series.points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  // The fill is closed along the bottom of the box rather than at the lowest
  // value: an area that starts at the minimum would make the smallest reading
  // look like nothing at all.
  const area = `${line} ${x(values.length - 1)},${height} 0,${height}`;
  // With no pointer the most recent value is the one marked: it is the reading
  // the tile prints beside the chart, so the mark and the number agree.
  const shown = active ?? values.length - 1;
  const point = series.points[shown];

  return (
    <div className="sparkline-wrap">
      <svg
        className="sparkline"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={describe(series)}
        style={{ color }}
      >
        {series.band && (
          <rect
            className="sparkline-band"
            x={0}
            y={Math.max(0, y(series.band.high))}
            width={width}
            height={Math.max(1, Math.min(height, y(series.band.low)) - Math.max(0, y(series.band.high)))}
          />
        )}

        {values.length > 1 && <polygon className="sparkline-area" points={area} />}
        {values.length > 1 && <polyline className="sparkline-line" points={line} />}

        {showDots &&
          series.points.map((p, index) => (
            <circle
              className={
                index === shown ? "sparkline-dot is-current" : "sparkline-dot"
              }
              key={p.sessionId}
              cx={x(index)}
              cy={y(p.value)}
              r={index === shown ? 4 : values.length > 20 ? 1.8 : 2.4}
            />
          ))}

        {/* The hit areas sit last so they take the pointer, and they are wider
            than the marks they stand for -- a 2px dot is not a target. One per
            point rather than a crosshair over the whole box, because the x
            axis here is a sequence of trainings and not a continuum: there is
            no value between two of them to read off. */}
        {interactive &&
          series.points.map((p, index) => (
            <rect
              key={`hit-${p.sessionId}`}
              className="sparkline-hit"
              x={index === 0 ? 0 : x(index) - width / (values.length - 1 || 1) / 2}
              y={0}
              width={width / (values.length > 1 ? values.length - 1 : 1)}
              height={height}
              onMouseEnter={() => setActive(index)}
              onMouseLeave={() => setActive(null)}
            />
          ))}
      </svg>

      {/* Not a floating tooltip: a line under the chart, which cannot cover the
          marks beside it and needs no positioning arithmetic. It says what the
          caller does not already print above the chart -- which training this
          point was -- so the figure appears here only under the pointer.

          The line is kept even when empty, because a tile that grows on hover
          nudges every tile after it. `aria-hidden`, since the chart's own
          accessible name already carries the numbers and the detail page
          repeats every point as a table: this is a convenience for the mouse,
          never the only place a value exists. */}
      {interactive && (
        <p className="sparkline-readout" aria-hidden="true">
          {active !== null && point && (
            <>
              <span className="sparkline-readout-value">
                {formatPoint(series, point.value)}
              </span>{" "}
              {formatDate(point.at) ?? point.at} · {point.scenario}
            </>
          )}
        </p>
      )}
    </div>
  );
}

/** The chart in words: how many trainings, the range they covered, and the
 *  most recent value. Stated, never judged. */
function describe(series: MetricSeries): string {
  const values = series.points.map((p) => p.value);
  const last = values[values.length - 1] ?? 0;
  const lowest = formatPoint(series, Math.min(...values));
  const highest = formatPoint(series, Math.max(...values));
  return (
    `${series.name}: ${values.length} Trainings, Werte von ${lowest} bis ${highest}, ` +
    `zuletzt ${formatPoint(series, last)}.`
  );
}
