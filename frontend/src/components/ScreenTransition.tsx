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
import ReverseCard from "./ReverseCard";

/**
 * The film cut between two screens: something covers the screen, the screen
 * changes behind it, the cover leaves.
 *
 * It lives above the router (see `main.tsx`) and not in whoever triggers it,
 * because the thing that triggers it is usually the thing that disappears —
 * a reverse started from a past training navigates to another route, and an
 * overlay rendered by that page would be unmounted halfway through its own
 * animation. Mounted once at the top, it plays out regardless of what the cut
 * did underneath it.
 *
 * Two of them. The reverse (F-61, ADR 0070) turns a card over, and is not
 * decoration for its own sake: the roles swapping is the one thing about that
 * feature a user has to understand before the call starts, and a card turning
 * over says it in a way the button's label cannot. The plain fade is the same
 * mechanism with nothing on it, for a cut that only wants the screen to go
 * dark and come back.
 */

/** How long each phase runs, by what is being played. The card needs the time
 * to turn; a fade that took as long would be a wait. */
const TIMING = {
  reverse: { cover: 620, reveal: 640 },
  fade: { cover: 300, reveal: 320 },
} as const;

type Kind = keyof typeof TIMING;

interface ScreenTransitionApi {
  /**
   * Play the reverse transition and run `cut` at the moment the screen is
   * covered. Everything the cut does — a state change, a navigation — is
   * invisible while it happens, which is the whole point of the cover.
   */
  playReverse: (cut: () => void) => void;
  /** The same, with no card: the screen dims, the cut happens, it comes back. */
  playFade: (cut: () => void) => void;
}

const ScreenTransitionContext = createContext<ScreenTransitionApi>({
  // No provider (a test rendering one screen on its own, say) means no
  // animation, never a missing screen change.
  playReverse: (cut) => cut(),
  playFade: (cut) => cut(),
});

export function useScreenTransition(): ScreenTransitionApi {
  return useContext(ScreenTransitionContext);
}

export function ScreenTransitionProvider({ children }: { children: ReactNode }) {
  const [run, setRun] = useState<{ cut: () => void; seq: number; kind: Kind } | null>(null);
  const [phase, setPhase] = useState<"cover" | "reveal">("cover");
  // Read in the two play functions, which have to stay referentially stable:
  // they sit in the dependency lists of the callbacks that start a call.
  const running = useRef(false);
  const seq = useRef(0);

  const play = useCallback((kind: Kind, cut: () => void) => {
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
    setRun({ cut, seq: seq.current, kind });
  }, []);

  const playReverse = useCallback((cut: () => void) => play("reverse", cut), [play]);
  const playFade = useCallback((cut: () => void) => play("fade", cut), [play]);

  useEffect(() => {
    if (!run) return undefined;
    const { cover, reveal } = TIMING[run.kind];
    const timers = [
      window.setTimeout(() => {
        run.cut();
        setPhase("reveal");
      }, cover),
      window.setTimeout(() => {
        running.current = false;
        setRun(null);
      }, cover + reveal),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, [run]);

  return (
    <ScreenTransitionContext.Provider value={{ playReverse, playFade }}>
      {children}
      {run && (
        <div
          // Keyed on the run so a repeat play restarts the animations rather
          // than continuing the previous element's.
          key={run.seq}
          className={`screen-transition screen-transition-${run.kind} screen-transition-${phase}`}
          // The durations live here and not in the stylesheet so the timers
          // above and the animations cannot drift apart.
          style={
            {
              "--cover-ms": `${TIMING[run.kind].cover}ms`,
              "--reveal-ms": `${TIMING[run.kind].reveal}ms`,
            } as CSSProperties
          }
          // Purely visual, and the screen behind it is already announced by
          // its own headings.
          aria-hidden="true"
        >
          <div className="screen-transition-scrim" />
          {run.kind === "reverse" && (
            <div className="screen-transition-card">
              <ReverseCard />
            </div>
          )}
        </div>
      )}
    </ScreenTransitionContext.Provider>
  );
}
