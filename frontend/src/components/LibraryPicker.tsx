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

/** "tenant" is labelled with the company name. */
const ORIGIN_LABELS: Record<Exclude<LibraryFilter, "tenant">, string> = {
  recommended: "Empfehlungen",
  all: "Alle",
  standard: "Standard",
  own: "Individuell",
  followUp: "Folgeszenario",
  reverse: "Rollentausch",
};

/** Two rows of three; the rest open from a button, never mistaken for a case. */
const COLLAPSED_TILES = 6;

/** Tells two reverses of one Scenario apart. */
function reverseSubtitle(card: ScenarioCard): string {
  if (!card.origin_session) return "Ursprungsgespräch gelöscht";
  const { started_at, persona } = card.origin_session;
  return `Gespräch vom ${formatDayMonth(started_at) ?? started_at} mit ${persona}`;
}

interface LibraryPickerProps {
  items: ScenarioCard[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: LibraryFilter;
  onFilter: (f: LibraryFilter) => void;
  originCounts: Record<LibraryFilter, number>;
  category: CategoryFilter;
  onCategory: (c: CategoryFilter) => void;
  categoryCounts: Record<CategoryFilter, number>;
  showRecommended: boolean;
  /** ADR 0060; null = no company option. */
  tenantName: string | null;
  newLabel: string;
  onNew: () => void;
  /** Editing is reached from the info panel (ADR 0062). */
  onInfo: (id: string) => void;
  /** F-62; the caller builds the drawable pool. */
  offerRandom?: boolean;
}

/** Also the `card-origin-` class suffix. The system-written kinds come first: both are `origin: "own"`. */
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

/** Two independent filter rows, a "new" button and badged cards (ADR 0058/0060/0062/0069). */
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
  // Collapsed again when the filters change.
  const [expanded, setExpanded] = useState(false);
  useEffect(() => setExpanded(false), [filter, category]);

  // The random tile takes one of the six places.
  const cards = offerRandom ? COLLAPSED_TILES - 1 : COLLAPSED_TILES;
  const hidden = items.length - cards;
  const shown = expanded ? items : items.slice(0, cards);
  const randomSelected = selectedId === RANDOM_SCENARIO_ID;

  const { focus } = useFocusContext();
  const goalTitle = (key: string) => focus?.goals.find((g) => g.key === key)?.title ?? key;

  const originOptions = LIBRARY_FILTERS.flatMap<FilterOption<LibraryFilter>>((f) => {
    // Only when there are suggestions: an empty chip is a broken promise (F-62).
    if (f === "recommended") {
      return showRecommended
        ? [{ value: f, label: ORIGIN_LABELS.recommended, count: originCounts.recommended }]
        : [];
    }
    // Only for a caller with colleagues (ADR 0060), named after the company.
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
        // Only when the grid is genuinely bare, random tile included.
        <p className="library-empty">Zu dieser Auswahl gibt es kein Szenario.</p>
      )}

      <div className="persona-grid scenario-grid">
        {/* First and fixed: nothing on screen leads to it. */}
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
              {/* Coloured by the card's origin class. */}
              <span className="card-badge">{badgeLabel(card, tenantName)}</span>
            </button>
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

      {/* "Alle", not "Weitere": everything is loaded, this only unfolds it. */}
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
