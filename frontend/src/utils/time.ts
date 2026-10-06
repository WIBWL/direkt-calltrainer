
/** The running timer: 0:00 until a full second has passed. */
export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Rounded, unlike the timer: this labels a past moment. */
export function formatOffset(offsetMs: number): string {
  return formatClock(Math.round(offsetMs / 1000));
}

/** Pinned, so a training shows the same clock time wherever it is opened. */
const DISPLAY_TIMEZONE = "Europe/Berlin";

/** E.g. "6. Sep 2026, 13:17"; null when there is nothing to format. */
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

/** E.g. "6. Sep. 2026". */
export function formatDate(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

/** E.g. "6. September 2026". */
export function formatLongDate(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "long",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

/** E.g. "6. September". */
export function formatDayMonth(iso: string | null | undefined): string | null {
  const at = parse(iso);
  if (!at) return null;
  return new Intl.DateTimeFormat("de-DE", {
    day: "numeric",
    month: "long",
    timeZone: DISPLAY_TIMEZONE,
  }).format(at);
}

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? null : at;
}
