/**
 * The F0 contour of a call, drawn the way phonetics draws it (F-35). Six
 * conventions, each a decision rather than a style:
 *
 * - **Semitones, relative to the speaker's own median.** Hertz is linear and
 *   pitch perception is not, so a Hertz axis draws the same intonation
 *   differently for a low and a high voice.
 * - **The horizontal axis is speaking time, not call time.** The curve holds
 *   the user's frames only, so no stretch of it stands for the Persona talking.
 *   Turn boundaries are dashed marks rather than gaps: the seam is a fact, dead
 *   space is not.
 * - **Unvoiced stretches are bridged, but drawn as bridges** — dotted and
 *   faint, and never across a seam. Holes broke the line into confetti; a
 *   silent interpolation would draw movement nobody measured, which is the
 *   commonest way an F0 plot lies.
 * - **Never more points than pixels.** Two minutes of speech is ~2400 points
 *   over 676 units; drawn one for one the line grows hair that is rendering
 *   noise. Above that density each column is reduced to its median.
 * - **The band is the speaker's own 5th-95th percentile**, measured at both
 *   ends rather than assumed symmetric, and it is not a target — it is the only
 *   comparison available without a norm nobody has measured (ADR 0051).
 * - **No colour carries meaning.** One hue throughout.
 */

const WIDTH = 720;
const HEIGHT = 232;
const PAD_LEFT = 46;
const PAD_BOTTOM = 28;
/** Room above the plot for the turn numbers. */
const PAD_TOP = 18;

/** Gridlines every three semitones: a minor third, small enough to read a
 *  contour against and large enough not to clutter. */
const GRID_STEP_ST = 3;
/** The axis never shrinks below this, so a monotone call looks monotone
 *  instead of being stretched to fill the box. */
const MIN_HALF_RANGE_ST = 4;
/** A little air above the highest and below the deepest point, so the extremes
 *  of a call do not sit exactly on the frame and read as clipped. */
const HEADROOM = 1.06;
/** One drawn point per unit of plot width; see the note on condensing. */
const MAX_POINTS = WIDTH - PAD_LEFT;
/** Below this spacing the turn numbers would sit on top of each other, and the
 *  dashed lines alone have to do the orienting. */
const MIN_LABEL_GAP = 26;

export default function PitchContour({
  curveHz,
  medianHz,
  stepMs,
  bandLowSt,
  bandHighSt,
  breaks = [],
}: {
  /** One point per `stepMs`, null where the frame carried no voicing. */
  curveHz: (number | null)[];
  /** The speaker's own middle, the zero of the vertical axis. */
  medianHz: number;
  /** The grid the curve is actually on, as the backend thinned it. */
  stepMs: number;
  /** The 5th and 95th percentile, in semitones from the median. */
  bandLowSt?: number | undefined;
  bandHighSt?: number | undefined;
  /** Indices into `curveHz` where one of the user's turns ends and the next
   *  begins. Empty for a Session measured before these were kept. */
  breaks?: number[] | undefined;
}) {
  const measured = curveHz.map((hz) => (hz ? 12 * Math.log2(hz / medianHz) : null));
  if (measured.filter((st) => st !== null).length < 2) return null;

  // The duration comes from what was measured, never from what is drawn: the
  // condensing below changes how many points there are, not how long the user
  // spoke.
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

  // Numbering the turns only helps while the numbers can be told apart.
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
          `Die Werte reichen von ${Math.min(...voiced).toFixed(1)} bis ` +
          `${Math.max(...voiced).toFixed(1)} Halbtönen um diese Mitte` +
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
            {/* Written out rather than mapped: on a perfectly steady voice the
                two ends are the same value, and a key of that value would be
                the same key twice. */}
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

        {/* Behind the curve: a seam is context for the line, not a thing to
            read on its own. */}
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

/**
 * The curve at no more than `maxPoints`, by taking each column's median.
 *
 * The median and not a mean or a sample: a mean would pull the value towards a
 * stray frame instead of ignoring it, and sampling one frame per column is what
 * turns a syllable rate into a sawtooth. A column with no voicing at all stays
 * empty, so the gaps survive the condensing, and the seams move with the points
 * they belong to.
 */
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
  // Deduplicated: two seams inside one column would draw two lines a hair
  // apart, and the caption counts them.
  const marks = [...new Set(breaks.map((index) => Math.round(index / per)))].filter(
    (index) => index > 0 && index < out.length,
  );
  return { points: out, marks };
}

/**
 * The curve as two sets of runs: what was measured, and what merely connects
 * two measured stretches. Both are needed because the line has to be continuous
 * to be readable and honest to be true.
 */
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
    // A run of one point draws nothing in SVG, and it is not lost: it stays the
    // endpoint of the bridges on either side of it.
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
