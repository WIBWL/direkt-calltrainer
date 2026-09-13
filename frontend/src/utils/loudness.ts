import { formatClock } from "./time";

/**
 * The reading behind F-37's loudness course: the curve with its jitter taken
 * out, the band drawn from the call's own samples, and the at most two
 * stretches that left it.
 *
 * Pure arithmetic, deliberately kept out of the component that used to own it:
 * the course is drawn twice now — as SVG on the feedback page
 * (`LoudnessCourse.tsx`) and into the downloadable report
 * (`utils/feedbackPdf.ts`) — and the two saying different things about the same
 * call would be worse than either being absent. The drawing is each renderer's
 * own; every number they draw comes from here.
 */

/** acoustics.py's `_SAMPLE_INTERVAL_MS` — the curve's only time base. */
export const MS_PER_POINT = 100;
/** Moving-average window, 1 s: syllables and word stress average out, a real
 * shift in level survives. */
const SMOOTH_POINTS = 10;
/** How long a departure has to hold (2 s) to be marked. Below that it is
 * delivery, not a change in how the call was conducted. */
const MIN_STRETCH_POINTS = 20;
/** How far outside the call's own spread a stretch has to sit, in multiples of
 * it. Self-referential on purpose — ADR 0051 declined to invent the norms a
 * fixed dB threshold would need. */
const DEVIATION = 2;
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

/** The reading, or null where there is nothing to read: a curve with fewer
 * than two audible samples has no course. */
export function analyseLoudness(values: (number | null)[]): LoudnessCurve | null {
  const audible = values.filter((value): value is number => value !== null);
  if (audible.length < 2) return null;

  const sorted = [...audible].sort((a, b) => a - b);
  const median = percentile(sorted, 0.5);
  const spread = robustSpread(sorted, median);

  const floor = sorted.reduce((least, value) => Math.min(least, value), Infinity);
  const ceiling = sorted.reduce((most, value) => Math.max(most, value), -Infinity);

  const smoothed = smooth(values);
  const low = median - DEVIATION * spread;
  const high = median + DEVIATION * spread;

  return {
    smoothed,
    points: values.length,
    median,
    low,
    high,
    floor,
    ceiling,
    span: ceiling - floor || 1,
    stretches: findStretches(smoothed, low, high),
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

/**
 * The width the band is built from. Kept in step with `_band` in
 * backend/feedback/metrics.py, which the wrap-up is written from — the two
 * disagreeing would put a sentence about a quieter stretch above a chart that
 * marks none.
 *
 * Median absolute deviation, not a percentile band: a stretch covering a third
 * of the call *is* the tenth percentile, so a percentile band goes blind to the
 * long shifts that matter most. Zero falls back to the mean deviation, which
 * vanishes only for a constant curve.
 */
function robustSpread(sorted: number[], median: number): number {
  const deviations = sorted.map((value) => Math.abs(value - median)).sort((a, b) => a - b);
  const middle = percentile(deviations, 0.5);
  if (middle > 0) return middle;
  return deviations.reduce((sum, value) => sum + value, 0) / (deviations.length || 1);
}

/** Linear-interpolated percentile of an already sorted series. */
function percentile(sorted: number[], fraction: number): number {
  const at = (sorted.length - 1) * fraction;
  const below = sorted[Math.floor(at)] ?? 0;
  const above = sorted[Math.ceil(at)] ?? below;
  return below + (above - below) * (at - Math.floor(at));
}

/** The curve with the jitter taken out. A window more than half silent yields
 * no value — its average would be the edge of the silence, not a spoken level. */
function smooth(values: (number | null)[]): (number | null)[] {
  const half = Math.floor(SMOOTH_POINTS / 2);
  return values.map((_, index) => {
    let sum = 0;
    let count = 0;
    for (let i = Math.max(0, index - half); i <= Math.min(values.length - 1, index + half); i++) {
      const value = values[i];
      if (value !== null && value !== undefined) {
        sum += value;
        count += 1;
      }
    }
    return count >= half ? sum / count : null;
  });
}

/**
 * At most one stretch per direction, the one that departed furthest over its
 * length: one marker each reads as "here it moved" rather than as a scatter of
 * every wobble.
 *
 * A call held evenly yields none — the band comes from its own samples, so a
 * steady speaker never leaves it. A flat call must not be given a variation.
 */
function findStretches(
  smoothed: (number | null)[],
  low: number,
  high: number,
): LoudnessStretch[] {
  const marked: (LoudnessDirection | null)[] = smoothed.map((value) => {
    if (value === null) return null;
    if (value > high) return "louder";
    if (value < low) return "quieter";
    return null;
  });

  const best: Partial<Record<LoudnessDirection, { deviation: number; peakIndex: number }>> = {};
  let index = 0;
  while (index < marked.length) {
    const direction = marked[index];
    if (!direction) {
      index += 1;
      continue;
    }
    let end = index;
    while (end < marked.length && marked[end] === direction) end += 1;

    if (end - index >= MIN_STRETCH_POINTS) {
      let deviation = 0;
      let peak = 0;
      let peakIndex = index;
      for (let i = index; i < end; i++) {
        const value = smoothed[i];
        if (value === null || value === undefined) continue;
        const distance = direction === "louder" ? value - high : low - value;
        deviation += distance;
        if (distance > peak) {
          peak = distance;
          peakIndex = i;
        }
      }
      const current = best[direction];
      if (!current || deviation > current.deviation) best[direction] = { deviation, peakIndex };
    }
    index = end;
  }

  return (["louder", "quieter"] as const).flatMap((direction) => {
    const found = best[direction];
    return found ? [{ direction, peakIndex: found.peakIndex }] : [];
  });
}
