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
