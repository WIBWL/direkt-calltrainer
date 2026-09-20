import { formatClock } from "./time";

/**
 * The reading behind F-37's loudness course, as the server derived it, plus the
 * arithmetic of drawing it.
 *
 * What is *read* off the curve — the band from the call's own samples, the
 * smoothing, the at most two stretches that left the band — is derived on every
 * read by `backend/feedback/readings.py` and arrives in the Measurement's
 * detail (ADR 0091). It used to be computed here as well, in a second
 * implementation in a second language, while the backend computed the same
 * thing to put one sentence about it into the wrap-up prompt. The two agreed by
 * care alone: a drawing that marked no quieter stretch under a sentence that
 * named one would have been nobody's fault in particular.
 *
 * What stays here is what the server has no business knowing: the extent of the
 * plot, where the line breaks for a silence, the clock under the axis, and the
 * words for a reader who cannot see it. The course is drawn twice — as SVG on
 * the feedback page (`LoudnessCourse.tsx`) and into the downloadable report
 * (`utils/feedbackPdf.ts`) — so those stay shared too.
 */

/** acoustics.py's `_SAMPLE_INTERVAL_MS` — the curve's only time base. */
const MS_PER_POINT = 100;
/** The longest silence the line is drawn through (2 s); see `loudnessRuns`. */
const BRIDGE_POINTS = 20;

export type LoudnessDirection = "louder" | "quieter";

export const LOUDNESS_CAPTION: Record<LoudnessDirection, string> = {
  louder: "lauter",
  quieter: "leiser",
};

export interface LoudnessStretch {
  direction: LoudnessDirection;
  /** Where the departure was largest — what the marker points at. */
  peakIndex: number;
}

export interface LoudnessCurve {
  /** The smoothed series, one point per `MS_PER_POINT`, `null` for silence. */
  smoothed: (number | null)[];
  /** How many points the raw series had — the horizontal extent. */
  points: number;
  median: number;
  /** The band's edges. */
  low: number;
  high: number;
  /** The vertical extent of the raw samples, and their span (never zero). */
  floor: number;
  ceiling: number;
  span: number;
  stretches: LoudnessStretch[];
  /** The user's own speaking time, as the axis labels it. */
  total: string;
}

/** One stretch as the wire names it (ADR 0057: English, snake_case). */
interface ServedStretch {
  direction: LoudnessDirection;
  peak_index: number;
}

interface ServedCourse {
  smoothed: (number | null)[];
  median: number;
  low: number;
  high: number;
  stretches: ServedStretch[];
}

/**
 * The course in one loudness Measurement's served detail, or null where there
 * is none to draw:
 * a Session stored before this was served, or a call with too little audible
 * speech for the server to read anything off.
 *
 * The plot's extent is worked out here rather than served: the floor, the
 * ceiling and the point count are the raw curve's own, and scaling a drawing is
 * not a judgement about the call.
 */
export function loudnessCourse(detail: Record<string, unknown> | null): LoudnessCurve | null {
  const values = detail?.["curve_db"] as (number | null)[] | undefined;
  const course = detail?.["course"] as ServedCourse | undefined;
  if (!values || !course) return null;

  const audible = values.filter((value): value is number => value !== null);
  if (audible.length < 2) return null;

  const floor = Math.min(...audible);
  const ceiling = Math.max(...audible);

  return {
    smoothed: course.smoothed,
    points: values.length,
    median: course.median,
    low: course.low,
    high: course.high,
    floor,
    ceiling,
    span: ceiling - floor || 1,
    stretches: course.stretches.map((stretch) => ({
      direction: stretch.direction,
      peakIndex: stretch.peak_index,
    })),
    total: formatClock((values.length * MS_PER_POINT) / 1000),
  };
}

/**
 * The line's runs of indices, drawn across the breathing pauses but not across
 * the silences.
 *
 * Gaps up to `BRIDGE_POINTS` are joined through: those are pauses inside an
 * utterance, and breaking at every one shattered the course into fragments. A
 * longer silence still ends the run — nothing was measured there, and a segment
 * across it would assert a level nobody spoke at. A run of one point is dropped
 * rather than returned: a line needs two.
 */
export function loudnessRuns(smoothed: (number | null)[]): number[][] {
  const out: number[][] = [];
  let run: number[] = [];
  let gap = 0;

  smoothed.forEach((value, index) => {
    if (value === null) {
      gap += 1;
      return;
    }
    if (gap > BRIDGE_POINTS) {
      if (run.length > 1) out.push(run);
      run = [];
    }
    gap = 0;
    run.push(index);
  });

  if (run.length > 1) out.push(run);
  return out;
}

/** What the picture says, for a reader who cannot see it. */
export function describeLoudness(curve: LoudnessCurve): string {
  const opening = `Lautstärkeverlauf über ${curve.total} Sprechzeit`;
  if (curve.stretches.length === 0) {
    return `${opening}: durchgehend im gewohnten Bereich, ohne längere Abweichung.`;
  }
  const parts = curve.stretches.map((stretch) => LOUDNESS_CAPTION[stretch.direction]);
  return `${opening}: ${parts.join(" an einer Stelle, ")} an einer Stelle.`;
}

/** Where on the user's own speaking clock a point sits. */
export function loudnessClock(index: number): string {
  return formatClock((index * MS_PER_POINT) / 1000);
}
