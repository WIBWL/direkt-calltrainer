/**
 * The F0 contour of a call, drawn the way phonetics draws it (F-35).
 *
 * Four conventions, each of which is a decision and not a style:
 *
 * **Semitones on the vertical axis, relative to the speaker's own median.**
 * Hertz is a linear scale and pitch perception is not: 20 Hz is a large step
 * for a low voice and a small one for a high voice, so a Hertz axis draws the
 * same intonation differently for two speakers. A semitone axis anchored at the
 * speaker's median is the standard normalisation and makes the picture about
 * the delivery rather than about the voice.
 *
 * **Gaps stay gaps.** Unvoiced frames are consonants, breaths and pauses, and
 * roughly half of speech carries no pitch at all. Interpolating across them
 * would draw movement that never happened, which is the single most common way
 * an F0 plot lies. The line breaks instead.
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
}: {
  /** One point per `stepMs`, null where the frame carried no voicing. */
  curveHz: (number | null)[];
  /** The speaker's own middle, the zero of the vertical axis. */
  medianHz: number;
  stepMs: number;
  /** The 5th and 95th percentile, in semitones from the median. */
  bandLowSt?: number | undefined;
  bandHighSt?: number | undefined;
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

  // One polyline per voiced run. The breaks are the point: see the docstring.
  const runs: string[] = [];
  let current: string[] = [];
  points.forEach((st, index) => {
    if (st === null) {
      if (current.length > 1) runs.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${x(index).toFixed(1)},${y(st).toFixed(1)}`);
  });
  if (current.length > 1) runs.push(current.join(" "));

  const gridlines: number[] = [];
  for (let st = -Math.floor(reach / GRID_STEP_ST) * GRID_STEP_ST; st <= reach; st += GRID_STEP_ST) {
    gridlines.push(st);
  }

  const seconds = (points.length * stepMs) / 1000;

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
          `${Math.max(...voiced).toFixed(1)} Halbtönen um diese Mitte.`
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

        {runs.map((run, index) => (
          <polyline className="pitch-contour-line" key={index} points={run} />
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
        Band ist der Bereich, in dem Sie meistens sprechen. Lücken sind stimmlose Stellen,
        also Konsonanten, Atem und Pausen; dort wird bewusst nicht durchgezeichnet.
      </figcaption>
    </figure>
  );
}
