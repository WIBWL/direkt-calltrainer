import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { useProgressData, type ProgressLoadState } from "./hooks/useProgressData";
import type { SessionSummary } from "./protocol";
import { CATEGORY_LABELS, type ScenarioCategory } from "./scenarioLibrary";
import { latest, readable, selectionSeries, type MetricSeries } from "./utils/progressStats";

/** Counted in trainings, not days. `prefix` begins the selection's sentence. */
export const PERIODS = [
  { key: "5", label: "Letzte 5", count: 5, prefix: "Ihren letzten 5" },
  { key: "10", label: "Letzte 10", count: 10, prefix: "Ihren letzten 10" },
  { key: "all", label: "Alle", count: null, prefix: "allen Ihren" },
] as const;

export type PeriodKey = (typeof PERIODS)[number]["key"];

/** ADR 0072: within one occasion a line is a series, not scatter. `noun` is dative plural. */
export const OCCASIONS = [
  { key: "all", label: "Alle Anlässe", category: null, noun: "Trainings" },
  {
    key: "operations",
    label: CATEGORY_LABELS.operations,
    category: "operations",
    noun: "Störungsgesprächen",
  },
  {
    key: "requirements",
    label: CATEGORY_LABELS.requirements,
    category: "requirements",
    noun: "Beratungsgesprächen",
  },
  {
    key: "pricing",
    label: CATEGORY_LABELS.pricing,
    category: "pricing",
    noun: "Preisgesprächen",
  },
  {
    key: "closing",
    label: CATEGORY_LABELS.closing,
    category: "closing",
    noun: "Abschlussgesprächen",
  },
] as const satisfies readonly {
  key: string;
  label: string;
  category: ScenarioCategory | null;
  noun: string;
}[];

export type OccasionKey = (typeof OCCASIONS)[number]["key"];

/** Also the fallback for an unknown URL value. */
const DEFAULT_PERIOD: PeriodKey = "all";
const DEFAULT_OCCASION: OccasionKey = "all";

const PERIOD_PARAM = "trainings";
const OCCASION_PARAM = "anlass";

interface ProgressContextValue {
  /** Every stored training, whatever the switches say. */
  sessions: SessionSummary[];
  selected: SessionSummary[];
  /** The denominator behind "aus N Trainings"; `series` is built from it. */
  readable: SessionSummary[];
  /** Derived once, so all three levels agree on which rows exist. */
  series: MetricSeries[];
  state: ProgressLoadState;
  truncated: boolean;
  total: number;
  period: PeriodKey;
  occasion: OccasionKey;
  periodPhrase: string;
  setPeriod: (key: PeriodKey) => void;
  setOccasion: (key: OccasionKey) => void;
  /** Shown on the switch, so nobody presses into an empty page. */
  occasionCounts: Record<OccasionKey, number>;
  /** Every link between the levels goes through this, keeping the selection. */
  withPeriod: (path: string) => string;
}

const ProgressContext = createContext<ProgressContextValue | null>(null);

/** Shared by the three dashboard screens (F-13). The selection lives in the URL. */
export function ProgressProvider({ children }: { children: ReactNode }) {
  const { sessions, state, truncated, total } = useProgressData();
  const [params, setParams] = useSearchParams();

  const option = readPeriod(params.get(PERIOD_PARAM));
  const period = option.key;
  const count = option.count;
  const occasionOption = readOccasion(params.get(OCCASION_PARAM));
  const occasion = occasionOption.key;
  const category = occasionOption.category;

  // Narrowed first, cut second, or "Letzte 5" plus "Beratung" could yield one.
  const selected = useMemo(
    () => latest(byOccasion(sessions, category), count),
    [sessions, category, count],
  );

  const readableSessions = useMemo(() => readable(selected), [selected]);
  const series = useMemo(() => selectionSeries(selected), [selected]);

  const occasionCounts = useMemo(() => {
    const counts = {} as Record<OccasionKey, number>;
    for (const entry of OCCASIONS) {
      counts[entry.key] = latest(byOccasion(sessions, entry.category), count).length;
    }
    return counts;
  }, [sessions, count]);

  const setParam = useCallback(
    (name: string, key: string, fallback: string) => {
      const next = new URLSearchParams(params);
      // The default stays out of the URL.
      if (key === fallback) next.delete(name);
      else next.set(name, key);
      // Replaced, so Back leaves the dashboard rather than undoing filters.
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const setPeriod = useCallback(
    (key: PeriodKey) => setParam(PERIOD_PARAM, key, DEFAULT_PERIOD),
    [setParam],
  );
  const setOccasion = useCallback(
    (key: OccasionKey) => setParam(OCCASION_PARAM, key, DEFAULT_OCCASION),
    [setParam],
  );

  const withPeriod = useCallback(
    (path: string) => {
      const query = new URLSearchParams();
      if (period !== DEFAULT_PERIOD) query.set(PERIOD_PARAM, period);
      if (occasion !== DEFAULT_OCCASION) query.set(OCCASION_PARAM, occasion);
      const text = query.toString();
      return text ? `${path}?${text}` : path;
    },
    [period, occasion],
  );

  const value = useMemo(
    () => ({
      sessions,
      selected,
      readable: readableSessions,
      series,
      state,
      truncated,
      total,
      period,
      occasion,
      periodPhrase: `${option.prefix} ${occasionOption.noun}`,
      setPeriod,
      setOccasion,
      occasionCounts,
      withPeriod,
    }),
    [
      sessions,
      selected,
      readableSessions,
      series,
      state,
      truncated,
      total,
      period,
      occasion,
      option.prefix,
      occasionOption.noun,
      setPeriod,
      setOccasion,
      occasionCounts,
      withPeriod,
    ],
  );

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>;
}

export function useProgressContext(): ProgressContextValue {
  const value = useContext(ProgressContext);
  if (!value) throw new Error("useProgressContext must be used inside <ProgressProvider>");
  return value;
}

function readPeriod(raw: string | null): (typeof PERIODS)[number] {
  const named = PERIODS.find((entry) => entry.key === raw);
  if (named) return named;
  const fallback = PERIODS.find((entry) => entry.key === DEFAULT_PERIOD);
  if (!fallback) throw new Error("no default period in PERIODS");
  return fallback;
}

/** Unknown values fall back to every occasion. */
function readOccasion(raw: string | null): (typeof OCCASIONS)[number] {
  const named = OCCASIONS.find((entry) => entry.key === raw);
  if (named) return named;
  const fallback = OCCASIONS.find((entry) => entry.key === DEFAULT_OCCASION);
  if (!fallback) throw new Error("no default occasion in OCCASIONS");
  return fallback;
}

/** Uncategorised trainings only ever count under "Alle Anlässe". */
function byOccasion(
  sessions: SessionSummary[],
  category: ScenarioCategory | null,
): SessionSummary[] {
  if (category === null) return sessions;
  return sessions.filter((session) => session.category === category);
}
