/**
 * Whether the viewer has asked their system for less motion.
 *
 * Read at the moment it matters rather than subscribed to: every caller asks
 * once, just before starting something that moves, and a setting changed
 * mid-animation should not cut that animation short.
 *
 * One place because two screens ask — the reverse's card cut (F-61) and the
 * random Scenario's die (F-62) — and because the query string is the kind of
 * thing that is quietly mistyped in a copy, where it fails open: a mistyped
 * media query matches nothing, so the motion plays and nobody notices.
 */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}
