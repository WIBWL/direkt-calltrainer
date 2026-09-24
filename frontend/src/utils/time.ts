/** Time values as the screens show them: mm:ss. No state, no DOM. */

/**
 * mm:ss for a whole number of elapsed seconds, the way the running call timer
 * counts them: 0:00 until a full second has actually passed.
 */
export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * A position on the Session's timeline, as mm:ss. Rounds to the nearest
 * second, unlike the timer above: this labels a past moment rather than
 * counting time that has gone by.
 */
export function formatOffset(offsetMs: number): string {
  return formatClock(Math.round(offsetMs / 1000));
}

/**
 * The timezone the interface reads in, pinned rather than left to the browser,
 * so a training shows the same clock time whoever opens it, wherever.
 */
const DISPLAY_TIMEZONE = "Europe/Berlin";

/**
 * Day and time, e.g. "6. Sep 2026, 13:17". Null, not a placeholder, when there is
 * nothing to format, so a caller can skip the row; placeholders are the caller's.
 */
export function formatDateTime(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

/** The day alone, e.g. "6. Sep. 2026". Null when there is nothing to format. */
export function formatDate(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

/** The long date, e.g. "6. September 2026", for a single prominent value. */
export function formatLongDate(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "long",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

/** Day and month without the year, e.g. "6. September", for a sentence that
 *  names a recent training. */
export function formatDayMonth(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    day: "numeric",
    month: "long",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

/** An ISO string as a Date, or null for anything unusable. */
function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? null : at;
}
