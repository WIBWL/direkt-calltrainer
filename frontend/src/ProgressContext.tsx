import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { useProgressData, type ProgressLoadState } from "./hooks/useProgressData";
import type { SessionSummary } from "./protocol";
import { latest } from "./utils/progressStats";

/**
 * Which trainings the dashboard is read over, counted in trainings (see
 * `progressStats.latest` for why not in days).
 *
 * It used to be 30 days, six months and everything. Six months is the retention
 * limit (ADR 0067), so the second and third said the same thing on almost every
 * account, and the first was empty for anybody who trains in bursts. The widest
 * option is still everything stored and nothing older.
 *
 * `phrase` is the same selection in a sentence, for the pages that are read
 * over it without carrying the switch itself.
 */
export const PERIODS = [
  { key: "5", label: "Letzte 5", count: 5, phrase: "Ihren letzten 5 Trainings" },
  { key: "10", label: "Letzte 10", count: 10, phrase: "Ihren letzten 10 Trainings" },
  { key: "all", label: "Alle", count: null, phrase: "allen Ihren Trainings" },
] as const;

export type PeriodKey = (typeof PERIODS)[number]["key"];

/**
 * Everything by default, as dashboard-konzept.md section 10 decided: the first
 * look should show all there is, and narrowing is one click away.
 *
 * Also what an unknown value in the URL falls back to. A hand-typed
 * `?trainings=42` is not an error worth a screen — it is a selection nobody
 * offered, and the widest one is the honest answer to it.
 */
const DEFAULT_PERIOD: PeriodKey = "all";

/** The selection's name in the URL. German, like every other path segment the
 *  user can see. */
const PERIOD_PARAM = "trainings";

interface ProgressContextValue {
  /** Every stored training, newest first, whatever the switch says. What the
   *  activity block at the top of the overview counts. */
  sessions: SessionSummary[];
  /** The trainings the switch selected — what every figure below it is read
   *  over, on the overview and on both detail levels alike. */
  selected: SessionSummary[];
  state: ProgressLoadState;
  /** True when the account holds more trainings than the dashboard reads. */
  truncated: boolean;
  total: number;
  period: PeriodKey;
  /** The current selection in a sentence ("Ihren letzten 5 Trainings"). */
  periodPhrase: string;
  setPeriod: (key: PeriodKey) => void;
  /** A dashboard path with the current selection on it. Every link between the
   *  three levels goes through this, which is what keeps them reading the same
   *  trainings. */
  withPeriod: (path: string) => string;
}

const ProgressContext = createContext<ProgressContextValue | null>(null);

/**
 * The trainings the dashboard reads, and which of them are selected, for all
 * three of its screens (F-13).
 *
 * Two things used to go wrong without it, and both were invisible:
 *
 * The overview, a metric's page and a goal's page each loaded the whole history
 * for themselves, so every step into a detail and back asked for it again and
 * showed "Wird geladen …" over a screen that had just been drawn.
 *
 * And the period switch reached only the overview. A tile said "aus 5
 * Trainings" and the page it linked to was drawn over every stored one —
 * two screens describing the same metric differently, which is exactly what
 * section 7 of dashboard-konzept.md rules out when it asks the detail level for
 * "alle Punkte des Zeitraums".
 *
 * The selection lives in the URL rather than in state here, so it survives a
 * reload and travels with a shared link — the reason section 7 gives for the
 * detail levels being routes at all.
 */
export function ProgressProvider({ children }: { children: ReactNode }) {
  const { sessions, state, truncated, total } = useProgressData();
  const [params, setParams] = useSearchParams();

  const option = readPeriod(params.get(PERIOD_PARAM));
  const period = option.key;
  const count = option.count;

  const selected = useMemo(() => latest(sessions, count), [sessions, count]);

  const setPeriod = useCallback(
    (key: PeriodKey) => {
      const next = new URLSearchParams(params);
      // The default stays out of the URL, so the plain path is the one people
      // copy and the parameter appears only where it says something.
      if (key === DEFAULT_PERIOD) next.delete(PERIOD_PARAM);
      else next.set(PERIOD_PARAM, key);
      // Replaced rather than pushed: Back should leave the dashboard, not undo
      // three presses of a filter first.
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const withPeriod = useCallback(
    (path: string) => (period === DEFAULT_PERIOD ? path : `${path}?${PERIOD_PARAM}=${period}`),
    [period],
  );

  const value = useMemo(
    () => ({
      sessions,
      selected,
      state,
      truncated,
      total,
      period,
      periodPhrase: option.phrase,
      setPeriod,
      withPeriod,
    }),
    [sessions, selected, state, truncated, total, period, option.phrase, setPeriod, withPeriod],
  );

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>;
}

/** The dashboard's data and its selection. Throws outside the provider, which
 *  is a wiring mistake and not a state a screen should try to draw. */
export function useProgressContext(): ProgressContextValue {
  const value = useContext(ProgressContext);
  if (!value) throw new Error("useProgressContext must be used inside <ProgressProvider>");
  return value;
}

/** The selection one URL asks for. Returns the option rather than the key, so
 *  the caller cannot look up a key that is not in the table. */
function readPeriod(raw: string | null): (typeof PERIODS)[number] {
  const named = PERIODS.find((entry) => entry.key === raw);
  if (named) return named;
  const fallback = PERIODS.find((entry) => entry.key === DEFAULT_PERIOD);
  // Unreachable while DEFAULT_PERIOD is one of the keys above, and the type
  // system cannot know that from a `find`.
  if (!fallback) throw new Error("no default period in PERIODS");
  return fallback;
}
