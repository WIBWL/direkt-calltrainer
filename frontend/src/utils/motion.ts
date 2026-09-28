/**
 * Whether the viewer's system asks for less motion, read just before something
 * moves rather than subscribed to. One place because a mistyped media query
 * fails open, silently playing the motion.
 */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}
