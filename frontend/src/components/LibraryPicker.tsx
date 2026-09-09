import { useEffect, useState } from "react";

import type { Origin, OriginSessionRef, ScenarioCategory } from "../scenarioLibrary";
import { CATEGORIES, CATEGORY_LABELS } from "../scenarioLibrary";
import FilterSlider, { type FilterOption } from "./FilterSlider";

/** Level 1, the origin of a Scenario: who it comes from. "followUp" is the
 * Folgeszenario drafted from a training (ADR 0069) and "reverse" the Rollentausch of one
 * finished Session (ADR 0070). Both are `origin: "own"` on the wire and options
 * of their own here — "Individuell" means hand-authored, and nothing else. Not
 * to be confused with the level-2 CategoryFilter below. */
export type LibraryFilter = "all" | "standard" | "own" | "followUp" | "reverse" | "tenant";

/** Level 2, the thematic category (ADR 0072). */
export type CategoryFilter = "all" | ScenarioCategory;

export const CATEGORY_FILTERS: CategoryFilter[] = ["all", ...CATEGORIES];

const CATEGORY_FILTER_LABELS: Record<CategoryFilter, string> = {
  all: "Alle",
  ...CATEGORY_LABELS,
};

/** Static labels; the "tenant" option is labelled with the company name. */
const ORIGIN_LABELS: Record<Exclude<LibraryFilter, "tenant">, string> = {
  all: "Alle",
  standard: "Standard",
  own: "Individuell",
  followUp: "Folgeszenario",
  reverse: "Rollentausch",
};

const BASE_ORIGINS = ["all", "standard", "own", "followUp", "reverse"] as const;

/** How many Scenario cards the grid shows before the "show all" tile takes over
 * the sixth place. Five and not six, so that tile is always on the first two
 * rows of a three-column grid rather than starting a third one by itself: the
 * seeded library alone is seventeen rows deep, and a selection screen that
 * opens on all of them is a scroll before it is a choice. */
const COLLAPSED_CARDS = 5;

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
   * own origin — "Individuell" means hand-authored. */
  followUp: boolean;
  /** A reverse of one finished Session (ADR 0070). */
  reverse: boolean;
  /** The conversation it replays; null once that Session has been deleted. */
  originSession: OriginSessionRef | null;
}

/** "Gespräch vom 3. September mit Anna Beck" — which conversation a reverse
 * replays, so two reverses of the same Scenario are told apart. */
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
  /** The caller's company name (ADR 0060); null = default tenant, no company
   * option or badge. */
  tenantName: string | null;
  newLabel: string;
  onNew: () => void;
  onEdit: (id: string) => void;
  /** Retire a reverse (ADR 0070), which is the only affordance it has in
   * place of editing. */
  onRemove: (id: string) => void;
}

/** Whether an item passes the active origin filter. "tenant" = anything shared
 * with the company, the author's own shared Scenarios included.
 *
 * A reverse is `origin: "own"` on the wire but is deliberately *not* under
 * "Individuell": that option means what the User wrote, and a reverse is a
 * copy of a call they had. Every Scenario therefore still sits under exactly
 * one origin option, which is what keeps the counts adding up. */
export function matchesFilter(item: LibraryItem, filter: LibraryFilter): boolean {
  if (filter === "all") return true;
  if (filter === "standard") return item.origin === "builtin";
  if (filter === "followUp") return item.followUp;
  if (filter === "reverse") return item.reverse;
  // "Individuell" is what is left of `own` once the two kinds the system wrote
  // itself are taken out, so every Scenario sits under exactly one option and
  // the counts add up.
  if (filter === "own") return item.origin === "own" && !item.followUp && !item.reverse;
  return item.shared;
}

/** Whether an item passes the active category filter. An uncategorised
 * Scenario matches only "all". There is no category it belongs to, and filing
 * it under one nobody chose would be a guess (ADR 0072). */
export function matchesCategory(item: LibraryItem, category: CategoryFilter): boolean {
  return category === "all" || item.category === category;
}

/** The card's origin, which is also its badge class suffix. Not the level-2
 * category — the prop of that name is the thematic filter.
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
 * The Scenario selection grid: two filter rows, a "new" button, badged cards,
 * and an edit affordance on the caller's own rows (ADR 0058 / 0060 / 0064 /
 * 0069).
 *
 * The rows are independent and combine. Level 1 says where a Scenario comes
 * from (Alle / Standard / Individuell / Folgeszenario / <Unternehmen>), level 2
 * says what kind of call it is. Both are the same component, so they are the
 * same size by construction.
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
  tenantName,
  newLabel,
  onNew,
  onEdit,
  onRemove,
}: LibraryPickerProps) {
  // Which card is asking to be confirmed, if any. One id rather than a set:
  // asking about a second row answers the first with "no", which is the safe
  // way round and saves a stray confirmation sitting armed on a card the User
  // has moved on from.
  const [confirmingRemoval, setConfirmingRemoval] = useState<string | null>(null);
  // The grid opens on one row and a half of cards; the rest is behind the tile
  // at the end of it. Collapsed again whenever the filters change, because what
  // "the first five" are has changed with them.
  const [expanded, setExpanded] = useState(false);
  useEffect(() => setExpanded(false), [filter, category]);

  const hidden = items.length - COLLAPSED_CARDS;
  const shown = expanded ? items : items.slice(0, COLLAPSED_CARDS);

  const originOptions: FilterOption<LibraryFilter>[] = [
    ...BASE_ORIGINS.map((f) => ({
      value: f as LibraryFilter,
      label: ORIGIN_LABELS[f],
      count: originCounts[f],
    })),
    // Only for a caller who has colleagues to share with (ADR 0060).
    ...(tenantName
      ? [{ value: "tenant" as LibraryFilter, label: tenantName, count: originCounts.tenant }]
      : []),
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
          <span className="scenario-library-filter-label">Herkunft</span>

          <FilterSlider
            options={originOptions}
            value={filter}
            onChange={onFilter}
            label="Szenarien nach Herkunft filtern"
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

      {items.length === 0 && (
        <p className="library-empty">
          {filter === "followUp"
            ? "Zu dieser Auswahl gibt es noch kein Folgeszenario."
            : filter === "reverse"
              ? "Noch kein Rollentausch. Sie erstellen einen nach einem Gespräch, unter der Auswertung."
              : "Zu dieser Auswahl gibt es kein Szenario."}
        </p>
      )}

      <div className="persona-grid scenario-grid">
        {shown.map((item) => (
          <div key={item.id} className="card-wrap">
            <button
              className={
                "persona-card" +
                (item.id === selectedId ? " selected" : "") +
                (item.origin === "own" ? " editable" : "")
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
              <span className={"card-badge card-badge-" + badgeClass(item)}>
                {badgeLabel(item, tenantName)}
              </span>
            </button>
            {/* A reverse is not editable (ADR 0070) — it copies a case that
                was played — so the affordance on it is removal instead, and
                that asks first: it sits where every other card carries
                "Bearbeiten", one slip away from a row the User cannot get
                back. Recreating it means going to the training it came from
                and spending a model call, if that training is even still
                stored. */}
            {item.reverse ? (
              confirmingRemoval === item.id ? (
                <span className="card-remove-confirm">
                  <button
                    type="button"
                    className="card-edit card-edit-danger"
                    onClick={() => {
                      setConfirmingRemoval(null);
                      onRemove(item.id);
                    }}
                  >
                    Ja, entfernen
                  </button>
                  <button
                    type="button"
                    className="card-edit"
                    onClick={() => setConfirmingRemoval(null)}
                  >
                    Abbrechen
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className="card-edit"
                  onClick={() => setConfirmingRemoval(item.id)}
                >
                  Entfernen
                </button>
              )
            ) : (
              item.origin === "own" && (
                <button type="button" className="card-edit" onClick={() => onEdit(item.id)}>
                  Bearbeiten
                </button>
              )
            )}
          </div>
        ))}

        {/* The tile in the sixth place, and a tile rather than a link under the
            grid: it is the last thing in the same row of choices, so it is
            found by the eye already reading them. Absent when everything is on
            screen — there is nothing behind it to open. */}
        {hidden > 0 && (
          <div className="card-wrap">
            <button
              type="button"
              className="persona-card library-more-card"
              onClick={() => setExpanded(!expanded)}
            >
              <span className="persona-name">
                {expanded ? "Weniger anzeigen" : "Alle anzeigen"}
              </span>
              <span className="card-subtitle">
                {expanded
                  ? `Zurück auf ${COLLAPSED_CARDS}`
                  : hidden === 1
                    ? "1 weiteres Szenario"
                    : `${hidden} weitere Szenarien`}
              </span>
            </button>
          </div>
        )}
      </div>
    </>
  );
}
