import { useEffect, useState } from "react";

import { useFocusContext } from "../FocusContext";
import type {
  Origin,
  OriginSessionRef,
  ScenarioCategory,
  ScenarioRecommendation,
} from "../scenarioLibrary";
import { CATEGORIES, CATEGORY_LABELS, RANDOM_SCENARIO_ID } from "../scenarioLibrary";
import FilterSlider, { type FilterOption } from "./FilterSlider";

/** Level 1, the origin of a Scenario: who it comes from. "followUp" is the
 * follow-up drafted from a training (ADR 0069) and "reverse" the Reverse of one
 * finished Session (ADR 0070). Both are `origin: "own"` on the wire and options
 * of their own here — the hand-authored option means exactly that, and nothing
 * else. Not to be confused with the level-2 CategoryFilter below. */
export type LibraryFilter =
  | "recommended" | "all" | "standard" | "own" | "followUp" | "reverse" | "tenant";

/** Level 2, the thematic category (ADR 0072). */
export type CategoryFilter = "all" | ScenarioCategory;

export const CATEGORY_FILTERS: CategoryFilter[] = ["all", ...CATEGORIES];

export const CATEGORY_FILTER_LABELS: Record<CategoryFilter, string> = {
  all: "Alle",
  ...CATEGORY_LABELS,
};

/** Static labels; the "tenant" option is labelled with the company name. */
const ORIGIN_LABELS: Record<Exclude<LibraryFilter, "tenant">, string> = {
  recommended: "Ihre Empfehlungen",
  all: "Alle",
  standard: "Standard",
  own: "Individuell",
  followUp: "Folgeszenario",
  reverse: "Rollentausch",
};

/** The order the chips are shown in, the company's among them rather than
 * appended after. Not the order of the grid — that is alphabetical — but the
 * order the kinds are met in: everything, then what ships, then what the User
 * wrote, then what their company shared, and last the two the system builds
 * out of a finished training, which exist only once there has been one. */
const ORIGIN_ORDER = ["all", "standard", "own", "tenant", "followUp", "reverse"] as const;

/** How many tiles the collapsed grid shows: two full rows of three. The seeded
 * library alone is seventeen rows deep, and a selection screen that opens on
 * all of them is a scroll before it is a choice.
 *
 * Every tile here is a case to pick — opening the rest is a button under the
 * grid instead (like the training history's), because it is not one of the
 * choices and reading it as a sixth case is a moment's confusion every time. */
const COLLAPSED_TILES = 6;

export interface LibraryItem {
  id: string;
  name: string;
  subtitle: string;
  origin: Origin;
  /** Shared with the company (own or a colleague's). */
  shared: boolean;
  /** F-03 call context, or null for an uncategorised Scenario (ADR 0072). */
  category: ScenarioCategory | null;
  /** Written from a Session's feedback (F-60) rather than by hand. Own, but its
   * own origin — the hand-authored option means exactly that. */
  followUp: boolean;
  /** A reverse of one finished Session (ADR 0070). */
  reverse: boolean;
  /** The conversation it replays; null once that Session has been deleted. */
  originSession: OriginSessionRef | null;
  /** Why it is suggested (F-62), or null if it is not. */
  recommendation: ScenarioRecommendation | null;
}

/** Why a card is suggested, in one line: that it matches the call types the
 *  User picked, and which of their focus goals it practises. */
export function recommendationReason(
  recommendation: ScenarioRecommendation,
  goalTitle: (key: string) => string,
): string {
  const parts: string[] = [];
  if (recommendation.call_type) parts.push("Passt zu Ihren Gesprächen");
  if (recommendation.goals.length > 0) {
    parts.push("Übt " + recommendation.goals.map((g) => `„${goalTitle(g)}“`).join(", "));
  }
  return parts.join(" · ");
}

/** Dates the call a reverse replays and names its Persona, so two reverses of
 * the same Scenario are told apart. */
function reverseSubtitle(item: LibraryItem): string {
  if (!item.originSession) return "Ursprungsgespräch gelöscht";
  const when = new Date(item.originSession.started_at).toLocaleDateString("de-DE", {
    day: "numeric",
    month: "long",
  });
  return `Gespräch vom ${when} mit ${item.originSession.persona}`;
}

interface LibraryPickerProps {
  items: LibraryItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Level 1: origin. */
  filter: LibraryFilter;
  onFilter: (f: LibraryFilter) => void;
  originCounts: Record<LibraryFilter, number>;
  /** Level 2: thematic category. */
  category: CategoryFilter;
  onCategory: (c: CategoryFilter) => void;
  categoryCounts: Record<CategoryFilter, number>;
  /** Whether anything is suggested; without a basis there is no such option. */
  showRecommended: boolean;
  /** The caller's company name (ADR 0060); null = default tenant, no company
   * option or badge. */
  tenantName: string | null;
  newLabel: string;
  onNew: () => void;
  /** Open the read-only info panel. Editing is reached from inside it
   * (ADR 0062), so the card carries no separate edit affordance. */
  onInfo: (id: string) => void;
  /** Offer the random Scenario tile (F-62). Decided by the caller, not here:
   * the tile draws only from the drawable rows among what these filters show
   * (`isDrawable`), and `items` does not say which those are — the caller holds
   * the cards that do. */
  offerRandom?: boolean;
}

/** Whether an item passes the active origin filter. "tenant" = anything shared
 * with the company, the author's own shared Scenarios included.
 *
 * A reverse is `origin: "own"` on the wire but is deliberately *not* under the
 * hand-authored option: that option means what the User wrote, and a reverse is
 * a copy of a call they had. Every Scenario sits under exactly one of the
 * origin options proper; "tenant" and "recommended" are views across them. */
export function matchesFilter(item: LibraryItem, filter: LibraryFilter): boolean {
  // A view over the cards, like the company option: a suggested Scenario stays
  // under its own origin too.
  if (filter === "recommended") return item.recommendation !== null;
  if (filter === "all") return true;
  if (filter === "standard") return item.origin === "builtin";
  if (filter === "followUp") return item.followUp;
  if (filter === "reverse") return item.reverse;
  // The hand-authored option is what is left of `own` once the two kinds the
  // system wrote itself are taken out.
  if (filter === "own") return item.origin === "own" && !item.followUp && !item.reverse;
  return item.shared;
}

/** Whether an item passes the active category filter. An uncategorised
 * Scenario matches only "all". There is no category it belongs to, and filing
 * it under one nobody chose would be a guess (ADR 0072). */
export function matchesCategory(item: LibraryItem, category: CategoryFilter): boolean {
  return category === "all" || item.category === category;
}

/** The card's origin, which is also the suffix of its `card-origin-` class —
 * the one that carries the colour of both the tile and its badge. Not the
 * level-2 category — the prop of that name is the thematic filter.
 *
 * The two kinds the system wrote itself come first: both are `origin: "own"`,
 * and that is the distinction the badge is making. */
function badgeClass(item: LibraryItem): string {
  if (item.reverse) return "reverse";
  if (item.followUp) return "follow-up";
  if (item.origin === "own") return item.shared ? "shared" : "own";
  return item.origin;
}

function badgeLabel(item: LibraryItem, tenantName: string | null): string {
  if (item.reverse) return "Rollentausch";
  if (item.followUp) return "Folgeszenario";
  if (item.origin === "own") return item.shared ? "Individuell · geteilt" : "Individuell";
  if (item.origin === "tenant") return tenantName ?? "Unternehmen";
  return "Standard";
}

/**
 * The Scenario selection grid: two filter rows, a "new" button, and badged
 * cards with an "i" that opens the info panel (ADR 0058 / 0060 / 0062 /
 * 0069).
 *
 * The rows are independent and combine. Level 1 says where a Scenario comes
 * from (suggested, all, built-in, hand-authored, the caller's company,
 * follow-up or reverse),
 * level 2 says what kind of call it is. Both are the same component, so they
 * are the same size by construction.
 */
export default function LibraryPicker({
  items,
  selectedId,
  onSelect,
  filter,
  onFilter,
  originCounts,
  category,
  onCategory,
  categoryCounts,
  showRecommended,
  tenantName,
  newLabel,
  onNew,
  onInfo,
  offerRandom = false,
}: LibraryPickerProps) {
  // The grid opens on `COLLAPSED_TILES`; the rest is behind the button under
  // it. Collapsed again whenever the filters change, because which rows come
  // first has changed with them.
  const [expanded, setExpanded] = useState(false);
  useEffect(() => setExpanded(false), [filter, category]);

  // The random tile is a case to pick like the others, so it takes one of the
  // six places rather than adding a seventh.
  const cards = offerRandom ? COLLAPSED_TILES - 1 : COLLAPSED_TILES;
  const hidden = items.length - cards;
  const shown = expanded ? items : items.slice(0, cards);
  const randomSelected = selectedId === RANDOM_SCENARIO_ID;

  const { focus } = useFocusContext();
  const goalTitle = (key: string) => focus?.goals.find((g) => g.key === key)?.title ?? key;

  const originOptions: FilterOption<LibraryFilter>[] = [
    // The suggestions lead the row, and only when there are any (F-62): a chip
    // that filters down to nothing is a promise the screen cannot keep. Outside
    // `ORIGIN_ORDER` because it is not a kind of Scenario but a view across
    // the kinds -- a suggested card keeps its origin and appears under both.
    ...(showRecommended
      ? [
          {
            value: "recommended" as LibraryFilter,
            label: ORIGIN_LABELS.recommended,
            count: originCounts.recommended,
          },
        ]
      : []),
    ...ORIGIN_ORDER.flatMap((f) => {
      // The company's chip is the one that can be absent — it is offered only
      // to a caller who has colleagues to share with (ADR 0060), and it is
      // labelled with the company's own name rather than a static word.
      // `flatMap` so it drops out of the middle of the row without leaving a
      // gap.
      if (f === "tenant") {
        return tenantName
          ? [{ value: f as LibraryFilter, label: tenantName, count: originCounts.tenant }]
          : [];
      }
      return [{ value: f as LibraryFilter, label: ORIGIN_LABELS[f], count: originCounts[f] }];
    }),
  ];

  const categoryOptions: FilterOption<CategoryFilter>[] = CATEGORY_FILTERS.map((c) => ({
    value: c,
    label: CATEGORY_FILTER_LABELS[c],
    count: categoryCounts[c],
  }));

  return (
    <>
      <div className="scenario-library-controls">
        <div className="scenario-library-controls-top">
          <span className="scenario-library-caption">Szenariobibliothek</span>

          <button type="button" className="library-new-button" onClick={onNew}>
            {newLabel}
          </button>
        </div>

        <div className="scenario-library-filter-row">
          <span className="scenario-library-filter-label">Szenariotyp</span>

          <FilterSlider
            options={originOptions}
            value={filter}
            onChange={onFilter}
            label="Szenarien nach Szenariotyp filtern"
          />
        </div>

        <div className="scenario-library-filter-row">
          <span className="scenario-library-filter-label">Gesprächsanlass</span>

          <FilterSlider
            options={categoryOptions}
            value={category}
            onChange={onCategory}
            label="Szenarien nach Kategorie filtern"
          />
        </div>
      </div>

      {items.length === 0 && !offerRandom && (
        // Only when the grid is genuinely bare. The pool is drawn from this
        // same filtered set, so an empty `items` already implies no tile — the
        // second condition is there because this line claiming an empty library
        // above a visible card is exactly what got it removed once before, and
        // that must not come back through a changed caller.
        <p className="library-empty">Zu dieser Auswahl gibt es kein Szenario.</p>
      )}

      <div className="persona-grid scenario-grid">
        {/* First, and in a fixed place: it is the one tile whose position must
            not move as the filters do, because nothing on screen leads to it.
            It is also the only card that says what it is *for* rather than what
            it is about — there is nothing to say about a case not yet drawn. */}
        {offerRandom && (
          <div className="card-wrap">
            <button
              type="button"
              className={
                "persona-card library-random-card card-origin-random" +
                (randomSelected ? " selected" : "")
              }
              onClick={() => onSelect(RANDOM_SCENARIO_ID)}
              aria-pressed={randomSelected}
            >
              <span className="choice-check" aria-hidden="true">
                {randomSelected ? "✓" : ""}
              </span>
              <span className="persona-name">Zufallsszenario</span>
              <span className="card-subtitle">
                Worum es geht, erfahren Sie erst im Gespräch — wie bei einem Anruf, der
                einfach hereinkommt.
              </span>
              <span className="card-badge">Überraschung</span>
            </button>
          </div>
        )}

        {shown.map((item) => (
          <div key={item.id} className="card-wrap">
            <button
              className={
                "persona-card card-origin-" + badgeClass(item) +
                (item.id === selectedId ? " selected" : "")
              }
              onClick={() => onSelect(item.id)}
              type="button"
              aria-pressed={item.id === selectedId}
            >
              <span className="choice-check" aria-hidden="true">
                {item.id === selectedId ? "✓" : ""}
              </span>
              <span className="persona-name">{item.name}</span>
              <span className="card-subtitle">
                {item.reverse ? reverseSubtitle(item) : item.subtitle}
              </span>
              {filter === "recommended" && item.recommendation && (
                <span className="card-reason">
                  {recommendationReason(item.recommendation, goalTitle)}
                </span>
              )}
              {/* Unclassed: its colours come from the card's own origin class,
                  so the badge and the tile it sits on cannot disagree. */}
              <span className="card-badge">{badgeLabel(item, tenantName)}</span>
            </button>
            {/* Every Scenario is readable (ADR 0062), so the "i" is on every
                card. */}
            <button
              type="button"
              className="card-info"
              onClick={() => onInfo(item.id)}
              aria-label={`Mehr über ${item.name}`}
              title={`Mehr über ${item.name}`}
            >
              <span aria-hidden="true">i</span>
            </button>

          </div>
        ))}
      </div>

      {/* Under the grid, not in it: it opens the rest of the library rather
          than being part of it. It looks like the training history's control
          but does less — everything is already here, so this only unfolds it,
          where that one fetches the next page. Hence "Alle" and not
          "Weitere": one press and the grid is complete. */}
      {hidden > 0 && (
        <button
          type="button"
          className="library-more"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
        >
          {expanded ? "Weniger anzeigen" : `Alle anzeigen (${items.length})`}
        </button>
      )}
    </>
  );
}
