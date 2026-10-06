import { formatClock } from "./time";

/** Drawing F-37's loudness course; the reading itself comes from the backend (ADR 0091). */

/** acoustics.py's `_SAMPLE_INTERVAL_MS`. */
const MS_PER_POINT = 100;
/** The longest silence the line is drawn through (2 s). */
const BRIDGE_POINTS = 20;

export type LoudnessDirection = "louder" | "quieter";

export const LOUDNESS_CAPTION: Record<LoudnessDirection, string> = {
  louder: "lauter",
  quieter: "leiser",
};

export interface LoudnessStretch {
  direction: LoudnessDirection;
  peakIndex: number;
}

export interface LoudnessCurve {
  /** `null` for silence. */
  smoothed: (number | null)[];
  points: number;
  median: number;
  low: number;
  high: number;
  /** Span never zero. */
  floor: number;
  ceiling: number;
  span: number;
  stretches: LoudnessStretch[];
  total: string;
}

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

/** Null with too little audible speech. */
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

/** Gaps up to `BRIDGE_POINTS` are joined; single points dropped. */
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

export function describeLoudness(curve: LoudnessCurve): string {
  const opening = `Lautstärkeverlauf über ${curve.total} Sprechzeit`;
  if (curve.stretches.length === 0) {
    return `${opening}: durchgehend im gewohnten Bereich, ohne längere Abweichung.`;
  }
  const parts = curve.stretches.map((stretch) => LOUDNESS_CAPTION[stretch.direction]);
  return `${opening}: ${parts.join(" an einer Stelle, ")} an einer Stelle.`;
}

export function loudnessClock(index: number): string {
  return formatClock((index * MS_PER_POINT) / 1000);
}
