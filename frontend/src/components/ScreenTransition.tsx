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

/** The cut between screens, above the router: the trigger may be what disappears. */

const TIMING = { cover: 300, reveal: 320 } as const;

interface ScreenTransitionApi {
  /** Runs `cut` while the screen is covered. */
  playFade: (cut: () => void) => void;
}

const ScreenTransitionContext = createContext<ScreenTransitionApi>({
  // Without a provider: no animation, never a missing change.
  playFade: (cut) => cut(),
});

export function useScreenTransition(): ScreenTransitionApi {
  return useContext(ScreenTransitionContext);
}

export function ScreenTransitionProvider({ children }: { children: ReactNode }) {
  const [run, setRun] = useState<{ cut: () => void; seq: number } | null>(null);
  const [phase, setPhase] = useState<"cover" | "reveal">("cover");
  // The play function must stay stable for the callbacks that start a call.
  const running = useRef(false);
  const seq = useRef(0);

  const playFade = useCallback((cut: () => void) => {
    // Do the cut, skip the film; a dropped cut is worse than no animation.
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
          key={run.seq}
          className={`screen-transition screen-transition-${phase}`}
          // Here, so the timers and animations cannot drift apart.
          style={
            {
              "--cover-ms": `${TIMING.cover}ms`,
              "--reveal-ms": `${TIMING.reveal}ms`,
            } as CSSProperties
          }
          aria-hidden="true"
        >
          <div className="screen-transition-scrim" />
        </div>
      )}
    </ScreenTransitionContext.Provider>
  );
}
