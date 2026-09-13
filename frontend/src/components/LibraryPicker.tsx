import { useEffect, useState } from "react";

import { useFocusContext } from "../FocusContext";
import {
  CATEGORY_FILTER_LABELS,
  CATEGORY_FILTERS,
  LIBRARY_FILTERS,
  RANDOM_SCENARIO_ID,
  recommendationReason,
  type CategoryFilter,
  type LibraryFilter,
  type ScenarioCard,
} from "../scenarioLibrary";
import { formatDayMonth } from "../utils/time";
import FilterSlider, { type FilterOption } from "./FilterSlider";

/** Static labels; the "tenant" option is labelled with the company name. */
const ORIGIN_LABELS: Record<Exclude<LibraryFilter, "tenant">, string> = {
  recommended: "Empfehlungen",
  all: "Alle",
  standard: "Standard",
  own: "Individuell",
  followUp: "Folgeszenario",
  reverse: "Rollentausch",
};

/** How many tiles the collapsed grid shows: two full rows of three. The seeded
 * library alone is seventeen rows deep, and a selection screen that opens on
 * all of them is a scroll before it is a choice.
 *
 * Every tile here is a case to pick — opening the rest is a button under the
 * grid instead (like the training history's), because it is not one of the
 * choices and reading it as a sixth case is a moment's confusion every time. */
const COLLAPSED_TILES = 6;

/** Dates the call a reverse replays and names its Persona, so two reverses of
 * the same Scenario are told apart. */
function reverseSubtitle(card: ScenarioCard): string {
  if (!card.origin_session) return "Ursprungsgespräch gelöscht";
  const { started_at, persona } = card.origin_session;
  return `Gespräch vom ${formatDayMonth(started_at) ?? started_at} mit ${persona}`;
}

interface LibraryPickerProps {
  items: ScenarioCard[];
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
   * (`isDrawable`), and the caller is where that pool is built. */
  offerRandom?: boolean;
}

/** The card's origin, which is also the suffix of its `card-origin-` class —
 * the one that carries the colour of both the tile and its badge. Not the
 * level-2 category — the prop of that name is the thematic filter.
 *
 * The two kinds the system wrote itself come first: both are `origin: "own"`,
 * and that is the distinction the badge is making. */
function badgeClass(card: ScenarioCard): string {
  if (card.reverse) return "reverse";
  if (card.follow_up) return "follow-up";
  if (card.origin === "own") return card.shared ? "shared" : "own";
  return card.origin;
}

function badgeLabel(card: ScenarioCard, tenantName: string | null): string {
  if (card.reverse) return "Rollentausch";
  if (card.follow_up) return "Folgeszenario";
  if (card.origin === "own") return card.shared ? "Individuell · geteilt" : "Individuell";
  if (card.origin === "tenant") return tenantName ?? "Unternehmen";
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
 * are the same size by construction. What each option matches is decided in
 * `scenarioLibrary.ts` (`matchesFilter`, `matchesCategory`), where the caller
 * builds the visible set and the counts from the same functions.
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

  const originOptions = LIBRARY_FILTERS.flatMap<FilterOption<LibraryFilter>>((f) => {
    // The suggestions lead the row, and only when there are any (F-62): a chip
    // that filters down to nothing is a promise the screen cannot keep.
    if (f === "recommended") {
      return showRecommended
        ? [{ value: f, label: ORIGIN_LABELS.recommended, count: originCounts.recommended }]
        : [];
    }
    // The company's chip is the other one that can be absent — it is offered
    // only to a caller who has colleagues to share with (ADR 0060), and it is
    // labelled with the company's own name rather than a static word.
    // `flatMap` so it drops out of the middle of the row without leaving a gap.
    if (f === "tenant") {
      return tenantName ? [{ value: f, label: tenantName, count: originCounts.tenant }] : [];
    }
    return [{ value: f, label: ORIGIN_LABELS[f], count: originCounts[f] }];
  });

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

        {shown.map((card) => (
          <div key={card.id} className="card-wrap">
            <button
              className={
                "persona-card card-origin-" + badgeClass(card) +
                (card.id === selectedId ? " selected" : "")
              }
              onClick={() => onSelect(card.id)}
              type="button"
              aria-pressed={card.id === selectedId}
            >
              <span className="choice-check" aria-hidden="true">
                {card.id === selectedId ? "✓" : ""}
              </span>
              <span className="persona-name">{card.name}</span>
              <span className="card-subtitle">
                {card.reverse ? reverseSubtitle(card) : card.short_description}
              </span>
              {filter === "recommended" && card.recommendation && (
                <span className="card-reason">
                  {recommendationReason(card.recommendation, goalTitle)}
                </span>
              )}
              {/* Unclassed: its colours come from the card's own origin class,
                  so the badge and the tile it sits on cannot disagree. */}
              <span className="card-badge">{badgeLabel(card, tenantName)}</span>
            </button>
            {/* Every Scenario is readable (ADR 0062), so the "i" is on every
                card. */}
            <button
              type="button"
              className="card-info"
              onClick={() => onInfo(card.id)}
              aria-label={`Mehr über ${card.name}`}
              title={`Mehr über ${card.name}`}
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
