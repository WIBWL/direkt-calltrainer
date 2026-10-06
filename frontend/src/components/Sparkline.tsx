import { useState } from "react";

import { colorOf } from "../utils/metricGroups";
import type { MetricSeries } from "../utils/progressStats";
import { formatPoint } from "../utils/progressStats";
import { formatDate } from "../utils/time";

/** One metric over the period (F-13) against the user's own usual range. No target,
 * colour judgement, arrow or trend line (ADR 0065). The accessible name carries the numbers. */
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
  /** Off inside a link, whose hit area it would fight. */
  interactive?: boolean;
}) {
  const [active, setActive] = useState<number | null>(null);
  const values = series.points.map((p) => p.value);
  if (values.length === 0) return null;

  const lowest = Math.min(...values, series.band?.low ?? Infinity);
  const highest = Math.max(...values, series.band?.high ?? -Infinity);
  // A flat series sits in the middle.
  const span = highest - lowest || Math.abs(highest) || 1;
  const pad = 6;
  const plot = height - pad * 2;
  const color = colorOf(series.aspect);

  const x = (index: number) =>
    values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
  const y = (value: number) => pad + plot - ((value - lowest) / span) * plot;

  const line = series.points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  // Closed at the bottom, or the smallest reading looks like nothing.
  const area = `${line} ${x(values.length - 1)},${height} 0,${height}`;
  // The latest by default, matching the printed figure.
  const shown = active ?? values.length - 1;
  const point = series.points[shown];

  return (
    <div className="sparkline-wrap">
      <div className="sparkline-plot">
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

          {/* Last, so they take the pointer; one per training, since there is nothing between two. */}
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

        {/* HTML over the stretched SVG, so the dots stay round. */}
        {showDots && (
          <div className="sparkline-dots" aria-hidden="true" style={{ color }}>
            {series.points.map((p, index) => {
              const diameter = index === shown ? 8 : values.length > 20 ? 3.6 : 4.8;
              return (
                <span
                  className={index === shown ? "sparkline-dot is-current" : "sparkline-dot"}
                  key={p.sessionId}
                  style={{
                    left: `${(x(index) / width) * 100}%`,
                    top: `${(y(p.value) / height) * 100}%`,
                    width: diameter,
                    height: diameter,
                  }}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* A line, not a tooltip; kept when empty so tiles do not shift. */}
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
