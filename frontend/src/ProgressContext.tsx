import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { useProgressData, type ProgressLoadState } from "./hooks/useProgressData";
import type { SessionSummary } from "./protocol";
import { CATEGORY_LABELS, type ScenarioCategory } from "./scenarioLibrary";
import { latest, selectionSeries, type MetricSeries } from "./utils/progressStats";

/**
 * Which trainings the dashboard is read over, counted in trainings (see
 * `progressStats.latest` for why not in days).
 *
 * It used to be 30 days, six months and everything. Six months is the retention
 * limit (ADR 0067), so the second and third said the same thing on almost every
 * account, and the first was empty for anybody who trains in bursts. The widest
 * option is still everything stored and nothing older.
 *
 * `prefix` is the selection's half of the sentence the pages without the switch
 * say themselves; the occasion below supplies the noun.
 */
export const PERIODS = [
  { key: "5", label: "Letzte 5", count: 5, prefix: "Ihren letzten 5" },
  { key: "10", label: "Letzte 10", count: 10, prefix: "Ihren letzten 10" },
  { key: "all", label: "Alle", count: null, prefix: "allen Ihren" },
] as const;

export type PeriodKey = (typeof PERIODS)[number]["key"];

/**
 * Which kind of call the dashboard is read over (ADR 0072's vocabulary).
 *
 * The answer to the concept's own strongest objection against its charts
 * (section 4.3): the trainings are not repeated measures. Scenario and Persona
 * move talk share, pace and the question count more than a change in behaviour
 * would, so a line across every training shows scatter while looking like
 * development. Narrowed to one occasion it is a series again, read against the
 * same kind of call — still the user's own past and nobody else's, which is the
 * only reference point ADR 0051 allows.
 *
 * It narrows and never judges: no occasion is the right one to train, and
 * nothing here compares two of them.
 *
 * `noun` is the dative plural the period's prefix takes ("Ihren letzten 5
 * Beratungsgesprächen"). It is not `CATEGORY_LABELS`, which names the occasion
 * of a call on a library card ("Beratung & Anforderung") and does not decline.
 */
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

/**
 * Everything by default, as dashboard-konzept.md section 10 decided: the first
 * look should show all there is, and narrowing is one click away.
 *
 * Also what an unknown value in the URL falls back to. A hand-typed
 * `?trainings=42` is not an error worth a screen — it is a selection nobody
 * offered, and the widest one is the honest answer to it.
 */
const DEFAULT_PERIOD: PeriodKey = "all";

/** Every occasion by default, for the reason the period defaults to everything:
 *  the first look should show all there is. Narrowing is one press away, and
 *  an account whose trainings are all of one kind sees the same page either
 *  way. */
const DEFAULT_OCCASION: OccasionKey = "all";

/** The selections' names in the URL. German, like every other path segment the
 *  user can see. */
const PERIOD_PARAM = "trainings";
const OCCASION_PARAM = "anlass";

interface ProgressContextValue {
  /** Every stored training, newest first, whatever the switches say. What the
   *  activity block at the top of the overview counts. */
  sessions: SessionSummary[];
  /** The trainings both switches selected — what every figure below them is
   *  read over, on the overview and on both detail levels alike. */
  selected: SessionSummary[];
  /** Every series `selected` has, the call length included — derived once
   *  here, so the overview and both detail levels cannot disagree about which
   *  rows exist (`selectionSeries`). */
  series: MetricSeries[];
  state: ProgressLoadState;
  /** True when the account holds more trainings than the dashboard reads. */
  truncated: boolean;
  total: number;
  period: PeriodKey;
  occasion: OccasionKey;
  /** The current selection in a sentence ("Ihren letzten 5
   *  Beratungsgesprächen"). */
  periodPhrase: string;
  setPeriod: (key: PeriodKey) => void;
  setOccasion: (key: OccasionKey) => void;
  /** How many trainings each occasion would yield under the current period, by
   *  key. The switch shows them, so nobody presses into an empty page. */
  occasionCounts: Record<OccasionKey, number>;
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
  const occasionOption = readOccasion(params.get(OCCASION_PARAM));
  const occasion = occasionOption.key;
  const category = occasionOption.category;

  // Narrowed first, cut second. The other order would take the last five
  // trainings and then keep whichever of them were advisory calls, so "Letzte
  // 5" plus "Beratung" could yield one — a selection whose size depends on
  // what was played in between, which is not what either switch says.
  const selected = useMemo(
    () => latest(byOccasion(sessions, category), count),
    [sessions, category, count],
  );

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
      // The default stays out of the URL, so the plain path is the one people
      // copy and the parameter appears only where it says something.
      if (key === fallback) next.delete(name);
      else next.set(name, key);
      // Replaced rather than pushed: Back should leave the dashboard, not undo
      // three presses of a filter first.
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

/** The same for the occasion. An unknown value falls back to every occasion
 *  rather than to none, for the reason the period does: a selection nobody
 *  offered is answered with the widest one, not with an error screen. */
function readOccasion(raw: string | null): (typeof OCCASIONS)[number] {
  const named = OCCASIONS.find((entry) => entry.key === raw);
  if (named) return named;
  const fallback = OCCASIONS.find((entry) => entry.key === DEFAULT_OCCASION);
  if (!fallback) throw new Error("no default occasion in OCCASIONS");
  return fallback;
}

/** The trainings of one kind of call, or all of them for null. An
 *  uncategorised training — an authored Scenario, a reverse — belongs to no
 *  occasion and is therefore only ever in "Alle Anlässe". Dropping it from
 *  every narrowed view is right: it is a training whose kind nobody recorded,
 *  and putting it under a heading it may not belong to would be the guess this
 *  filter exists to avoid. */
function byOccasion(
  sessions: SessionSummary[],
  category: ScenarioCategory | null,
): SessionSummary[] {
  if (category === null) return sessions;
  return sessions.filter((session) => session.category === category);
}
