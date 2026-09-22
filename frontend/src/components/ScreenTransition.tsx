import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { prefersReducedMotion } from "../utils/motion";

/**
 * The film cut between two screens: the screen dims to opaque, changes behind
 * the cover, and comes back.
 *
 * Lives above the router (see `main.tsx`) rather than in whoever triggers it,
 * because the trigger may be the thing that disappears: an overlay rendered by
 * a page that navigates away would unmount halfway through its own animation.
 * Mounted once at the top, it plays out regardless of what the cut did
 * underneath.
 */

/** How long each phase runs. Long enough to read as a cut, short enough not to
 * be a wait. */
const TIMING = { cover: 300, reveal: 320 } as const;

interface ScreenTransitionApi {
  /**
   * Dim the screen and run `cut` at the moment it is covered. Everything the
   * cut does — a state change, a navigation — is invisible while it happens,
   * which is the whole point of the cover.
   */
  playFade: (cut: () => void) => void;
}

const ScreenTransitionContext = createContext<ScreenTransitionApi>({
  // No provider (a test rendering one screen on its own, say) means no
  // animation, never a missing screen change.
  playFade: (cut) => cut(),
});

export function useScreenTransition(): ScreenTransitionApi {
  return useContext(ScreenTransitionContext);
}

export function ScreenTransitionProvider({ children }: { children: ReactNode }) {
  const [run, setRun] = useState<{ cut: () => void; seq: number } | null>(null);
  const [phase, setPhase] = useState<"cover" | "reveal">("cover");
  // Read in the play function, which has to stay referentially stable: it
  // sits in the dependency lists of the callbacks that start a call.
  const running = useRef(false);
  const seq = useRef(0);

  const playFade = useCallback((cut: () => void) => {
    // Reduced motion and a second press while one is already playing take the
    // same way out: do the cut, skip the film. A dropped cut would leave the
    // press without an effect, which is the one outcome worse than no
    // animation.
    if (running.current || prefersReducedMotion()) {
      cut();
      return;
    }
    running.current = true;
    seq.current += 1;
    setPhase("cover");
    setRun({ cut, seq: seq.current });
  }, []);

  useEffect(() => {
    if (!run) return undefined;
    const timers = [
      window.setTimeout(() => {
        run.cut();
        setPhase("reveal");
      }, TIMING.cover),
      window.setTimeout(() => {
        running.current = false;
        setRun(null);
      }, TIMING.cover + TIMING.reveal),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, [run]);

  return (
    <ScreenTransitionContext.Provider value={{ playFade }}>
      {children}
      {run && (
        <div
          // Keyed on the run so a repeat play restarts the animations rather
          // than continuing the previous element's.
          key={run.seq}
          className={`screen-transition screen-transition-${phase}`}
          // The durations live here and not in the stylesheet so the timers
          // above and the animations cannot drift apart.
          style={
            {
              "--cover-ms": `${TIMING.cover}ms`,
              "--reveal-ms": `${TIMING.reveal}ms`,
            } as CSSProperties
          }
          // Purely visual, and the screen behind it is already announced by
          // its own headings.
          aria-hidden="true"
        >
          <div className="screen-transition-scrim" />
        </div>
      )}
    </ScreenTransitionContext.Provider>
  );
}
