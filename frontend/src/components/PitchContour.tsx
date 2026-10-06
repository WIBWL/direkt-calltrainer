/** The F0 contour (F-35): semitones from the speaker's median over their own
 * speaking time, dashed turn seams, unvoiced gaps bridged dotted. The band is the
 * speaker's own 5th-95th percentile, not a target (ADR 0051). */

import { formatNumber } from "../utils/metrics";

const WIDTH = 720;
const HEIGHT = 232;
const PAD_LEFT = 46;
const PAD_BOTTOM = 28;
const PAD_TOP = 18;

/** A minor third. */
const GRID_STEP_ST = 3;
/** So a monotone call looks monotone rather than stretched. */
const MIN_HALF_RANGE_ST = 4;
const HEADROOM = 1.06;
/** One drawn point per unit of plot width. */
const MAX_POINTS = WIDTH - PAD_LEFT;
const MIN_LABEL_GAP = 26;

export default function PitchContour({
  curveHz,
  medianHz,
  stepMs,
  bandLowSt,
  bandHighSt,
  breaks = [],
}: {
  curveHz: (number | null)[];
  medianHz: number;
  stepMs: number;
  bandLowSt?: number | undefined;
  bandHighSt?: number | undefined;
  breaks?: number[] | undefined;
}) {
  const measured = curveHz.map((hz) => (hz ? 12 * Math.log2(hz / medianHz) : null));
  if (measured.filter((st) => st !== null).length < 2) return null;

  // From what was measured; condensing changes the points, not the duration.
  const seconds = (measured.length * stepMs) / 1000;
  const { points, marks } = condense(
    measured,
    breaks.filter((index) => index > 0 && index < measured.length),
    MAX_POINTS,
  );

  const voiced = points.filter((st): st is number => st !== null);
  const reach = Math.max(
    MIN_HALF_RANGE_ST,
    ...voiced.map((st) => Math.abs(st) * HEADROOM),
  );
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const plotWidth = WIDTH - PAD_LEFT;
  const x = (index: number) => PAD_LEFT + (index / (points.length - 1)) * plotWidth;
  const y = (st: number) => PAD_TOP + plotHeight / 2 - (st / reach) * (plotHeight / 2);

  const { lines, bridges } = trace(points, marks);
  const path = (run: [number, number][]) =>
    run.map(([index, st]) => `${x(index).toFixed(1)},${y(st).toFixed(1)}`).join(" ");

  const gridlines: number[] = [];
  for (let st = -Math.floor(reach / GRID_STEP_ST) * GRID_STEP_ST; st <= reach; st += GRID_STEP_ST) {
    gridlines.push(st);
  }

  const gaps = marks.map(
    (mark, position) => x(mark) - (position === 0 ? PAD_LEFT : x(marks[position - 1]!)),
  );
  const numbered = marks.length > 0 && Math.min(...gaps) >= MIN_LABEL_GAP;

  return (
    <figure className="pitch-contour">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="pitch-contour-plot"
        role="img"
        aria-label={
          `Tonhöhenverlauf über ${Math.round(seconds)} Sekunden Sprechzeit, ` +
          `bezogen auf Ihre mittlere Stimmlage von ${Math.round(medianHz)} Hertz. ` +
          `Die Werte reichen von ${formatNumber(Math.min(...voiced), 1)} bis ` +
          `${formatNumber(Math.max(...voiced), 1)} Halbtönen um diese Mitte` +
          (marks.length > 0
            ? `, verteilt auf ${marks.length + 1} Redebeiträge von Ihnen.`
            : ".")
        }
      >
        {bandLowSt !== undefined && bandHighSt !== undefined && (
          <>
            <rect
              className="pitch-contour-band"
              x={PAD_LEFT}
              y={y(bandHighSt)}
              width={plotWidth}
              height={Math.max(1, y(bandLowSt) - y(bandHighSt))}
            />
            {/* Not mapped: on a steady voice both ends share a value, and so a key. */}
            <line
              className="pitch-contour-band-edge"
              x1={PAD_LEFT}
              y1={y(bandHighSt)}
              x2={WIDTH}
              y2={y(bandHighSt)}
            />
            <line
              className="pitch-contour-band-edge"
              x1={PAD_LEFT}
              y1={y(bandLowSt)}
              x2={WIDTH}
              y2={y(bandLowSt)}
            />
          </>
        )}

        {gridlines.map((st) => (
          <g key={st}>
            <line
              className={st === 0 ? "pitch-contour-median" : "pitch-contour-grid"}
              x1={PAD_LEFT}
              y1={y(st)}
              x2={WIDTH}
              y2={y(st)}
            />
            <text className="pitch-contour-tick" x={PAD_LEFT - 6} y={y(st) + 3.4}>
              {st === 0 ? "Ihre Mitte" : `${st > 0 ? "+" : ""}${st}`}
            </text>
          </g>
        ))}

        {marks.map((index, position) => (
          <g key={index}>
            <line
              className="pitch-contour-break"
              x1={x(index)}
              y1={PAD_TOP - 6}
              x2={x(index)}
              y2={PAD_TOP + plotHeight}
            />
            {numbered && (
              <text className="pitch-contour-turn" x={x(index) + 3} y={PAD_TOP - 8}>
                {position + 2}.
              </text>
            )}
          </g>
        ))}

        {numbered && (
          <text className="pitch-contour-turn" x={PAD_LEFT + 3} y={PAD_TOP - 8}>
            1. Redebeitrag
          </text>
        )}

        {bridges.map((run, index) => (
          <polyline className="pitch-contour-bridge" key={index} points={path(run)} />
        ))}

        {lines.map((run, index) => (
          <polyline className="pitch-contour-line" key={index} points={path(run)} />
        ))}

        <text className="pitch-contour-axis-label" x={PAD_LEFT} y={HEIGHT - 8}>
          0 s
        </text>
        <text className="pitch-contour-axis-label pitch-contour-axis-end" x={WIDTH} y={HEIGHT - 8}>
          {Math.round(seconds)} s Ihrer Sprechzeit
        </text>
      </svg>

      <figcaption className="pitch-contour-legend">
        Halbtöne um Ihre mittlere Stimmlage ({Math.round(medianHz)} Hz, die Nulllinie). Das Band
        ist der Bereich, in dem Sie meistens gesprochen haben, kein Zielbereich. Waagerecht
        läuft nur Ihre eigene Sprechzeit; die gepunkteten Stücke überbrücken stimmlose Stellen
        wie Konsonanten und Atem, dort wurde nichts gemessen.
        {marks.length > 0 && (
          <>
            {" "}
            Die gestrichelten Linien markieren, wo einer Ihrer Redebeiträge endet und der nächste
            beginnt. Dazwischen sprach Ihr Gegenüber; diese Zeit ist nicht dargestellt.
          </>
        )}
      </figcaption>
    </figure>
  );
}

/** Each column's median: a mean is pulled by stray frames, and sampling turns a
 * syllable rate into a sawtooth. Unvoiced columns stay empty. */
function condense(
  points: (number | null)[],
  breaks: number[],
  maxPoints: number,
): { points: (number | null)[]; marks: number[] } {
  if (points.length <= maxPoints) return { points, marks: breaks };

  const per = points.length / maxPoints;
  const out: (number | null)[] = [];
  for (let column = 0; column < maxPoints; column++) {
    const from = Math.floor(column * per);
    const to = Math.max(from + 1, Math.floor((column + 1) * per));
    const values = points.slice(from, to).filter((st): st is number => st !== null);
    values.sort((a, b) => a - b);
    out.push(values.length > 0 ? values[Math.floor(values.length / 2)]! : null);
  }
  // Two seams in one column would draw twice; the caption counts them.
  const marks = [...new Set(breaks.map((index) => Math.round(index / per)))].filter(
    (index) => index > 0 && index < out.length,
  );
  return { points: out, marks };
}

/** What was measured, and what merely connects two measured stretches. */
function trace(
  points: (number | null)[],
  marks: number[],
): { lines: [number, number][][]; bridges: [number, number][][] } {
  const seams = new Set(marks);
  const lines: [number, number][][] = [];
  const bridges: [number, number][][] = [];

  let run: [number, number][] = [];
  let previous: [number, number] | null = null;

  const closeRun = () => {
    // A single point draws nothing; it stays the end of the bridges beside it.
    if (run.length > 1) lines.push(run);
    run = [];
  };

  for (let index = 0; index < points.length; index++) {
    if (seams.has(index)) {
      closeRun();
      previous = null; // the voice did not travel across a seam, so no bridge
    }
    const st = points[index];
    if (st === null || st === undefined) {
      closeRun();
      continue;
    }

    const point: [number, number] = [index, st];
    if (run.length === 0 && previous !== null) {
      bridges.push([previous, point]);
    }
    run.push(point);
    previous = point;
  }
  closeRun();

  return { lines, bridges };
}
