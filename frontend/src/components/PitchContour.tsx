/**
 * The F0 contour of a call, drawn the way phonetics draws it (F-35).
 *
 * Five conventions, each of which is a decision and not a style:
 *
 * **Semitones on the vertical axis, relative to the speaker's own median.**
 * Hertz is a linear scale and pitch perception is not: 20 Hz is a large step
 * for a low voice and a small one for a high voice, so a Hertz axis draws the
 * same intonation differently for two speakers. A semitone axis anchored at the
 * speaker's median is the standard normalisation and makes the picture about
 * the delivery rather than about the voice.
 *
 * **The horizontal axis is speaking time, not call time.** The curve holds the
 * user's frames only; what the Persona said is not in the data at all, so no
 * stretch of this plot stands for someone else talking. Where one utterance
 * ends and the next begins there is a dashed mark instead of a gap — the seam
 * is a fact worth seeing, an empty stretch would only be dead space.
 *
 * **Unvoiced stretches are bridged, but drawn as bridges.** Roughly half of
 * speech carries no pitch: consonants, breaths, the pauses inside a sentence.
 * Leaving them as holes broke the line into confetti and made a contour
 * unreadable at a glance; interpolating them silently would draw movement that
 * was never measured, which is the commonest way an F0 plot lies. So the line
 * runs through, and the bridged pieces are thin and faint: continuous to
 * follow, visibly not the same claim as the measured stretches.
 *
 * **The band is the speaker's own 5th to 95th percentile**, not a target. It is
 * there so the eye can see which excursions were unusual *for this speaker*,
 * which is the only comparison available without a norm nobody has measured
 * (ADR 0051).
 *
 * **No colour carries meaning.** One hue throughout, as everywhere else in this
 * application except the single trialled traffic light.
 */

const WIDTH = 720;
const HEIGHT = 220;
const PAD_LEFT = 38;
const PAD_BOTTOM = 26;
const PAD_TOP = 10;

/** Gridlines every three semitones: a minor third, small enough to read a
 *  contour against and large enough not to clutter. */
const GRID_STEP_ST = 3;
/** The axis never shrinks below this, so a monotone call looks monotone
 *  instead of being stretched to fill the box. */
const MIN_HALF_RANGE_ST = 4;

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
  stepMs: number;
  /** The 5th and 95th percentile, in semitones from the median. */
  bandLowSt?: number | undefined;
  bandHighSt?: number | undefined;
  /** Indices into `curveHz` where one utterance ends and the next begins.
   *  Empty for a Session measured before these were kept. */
  breaks?: number[] | undefined;
}) {
  const points = curveHz.map((hz) => (hz ? 12 * Math.log2(hz / medianHz) : null));
  const voiced = points.filter((st): st is number => st !== null);
  if (voiced.length < 2) return null;

  const reach = Math.max(
    MIN_HALF_RANGE_ST,
    ...voiced.map((st) => Math.abs(st)),
  );
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const plotWidth = WIDTH - PAD_LEFT;
  const x = (index: number) => PAD_LEFT + (index / (points.length - 1)) * plotWidth;
  const y = (st: number) => PAD_TOP + plotHeight / 2 - (st / reach) * (plotHeight / 2);

  const marks = breaks.filter((index) => index > 0 && index < points.length);
  const { lines, bridges } = trace(points, marks);

  const gridlines: number[] = [];
  for (let st = -Math.floor(reach / GRID_STEP_ST) * GRID_STEP_ST; st <= reach; st += GRID_STEP_ST) {
    gridlines.push(st);
  }

  const seconds = (points.length * stepMs) / 1000;
  const path = (run: [number, number][]) =>
    run.map(([index, st]) => `${x(index).toFixed(1)},${y(st).toFixed(1)}`).join(" ");

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
            ? `, aufgeteilt auf ${marks.length + 1} Redebeiträge von Ihnen.`
            : ".")
        }
      >
        {bandLowSt !== undefined && bandHighSt !== undefined && (
          <rect
            className="pitch-contour-band"
            x={PAD_LEFT}
            y={y(bandHighSt)}
            width={plotWidth}
            height={Math.max(1, y(bandLowSt) - y(bandHighSt))}
          />
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
            <text className="pitch-contour-tick" x={PAD_LEFT - 6} y={y(st) + 3.5}>
              {st > 0 ? `+${st}` : st}
            </text>
          </g>
        ))}

        {/* Behind the curve: a seam is context for the line, not a thing to
            read on its own. */}
        {marks.map((index) => (
          <line
            className="pitch-contour-break"
            key={index}
            x1={x(index)}
            y1={PAD_TOP}
            x2={x(index)}
            y2={PAD_TOP + plotHeight}
          />
        ))}

        {bridges.map((run, index) => (
          <polyline className="pitch-contour-bridge" key={index} points={path(run)} />
        ))}

        {lines.map((run, index) => (
          <polyline className="pitch-contour-line" key={index} points={path(run)} />
        ))}

        <text className="pitch-contour-axis-label" x={2} y={PAD_TOP + 8}>
          HT
        </text>
        <text className="pitch-contour-axis-label" x={PAD_LEFT} y={HEIGHT - 6}>
          0 s
        </text>
        <text className="pitch-contour-axis-label pitch-contour-axis-end" x={WIDTH} y={HEIGHT - 6}>
          {Math.round(seconds)} s Sprechzeit
        </text>
      </svg>

      <figcaption className="pitch-contour-legend">
        Halbtöne um Ihre mittlere Stimmlage ({Math.round(medianHz)} Hz, die Nulllinie). Das
        Band ist der Bereich, in dem Sie meistens sprechen. Waagerecht läuft nur Ihre eigene
        Sprechzeit; die dünnen Verbindungen überbrücken stimmlose Stellen wie Konsonanten und
        Atem, dort wurde nichts gemessen.
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
 * The curve as two sets of runs: what was measured, and what merely connects
 * two measured stretches.
 *
 * Both are needed because the line has to be continuous to be readable and
 * honest to be true. A bridge is emitted for every unvoiced stretch inside one
 * utterance, and never across an utterance seam: the voice did not travel from
 * the end of one turn to the start of the next, the Persona spoke in between.
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

  points.forEach((st, index) => {
    if (seams.has(index)) {
      closeRun();
      previous = null; // the voice did not travel across a seam, so no bridge
    }
    if (st === null) {
      closeRun();
      return;
    }

    const point: [number, number] = [index, st];
    if (run.length === 0 && previous !== null) {
      bridges.push([previous, point]);
    }
    run.push(point);
    previous = point;
  });
  closeRun();

  return { lines, bridges };
}
