import { formatClock } from "./time";

/** Drawing F-37's loudness course. The reading (band, smoothing, stretches) comes
 * from `backend/feedback/readings.py` (ADR 0091) — do not recompute it here.
 * This holds only the drawing: extent, line breaks, axis clock and text
 * alternative, shared by `LoudnessCourse.tsx` and `utils/feedbackPdf.ts`. */

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
 * The course in a loudness Measurement's served detail, or null (an older
 * Session, or too little audible speech). The plot's extent is computed here:
 * scaling a drawing is no judgement about the call.
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
 * The line's runs of indices: gaps up to `BRIDGE_POINTS` (pauses inside an
 * utterance) are joined; a longer silence ends the run, since nothing was
 * measured there. Single-point runs are dropped: a line needs two.
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
