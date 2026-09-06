import type { Origin, ScenarioCategory } from "../scenarioLibrary";
import { CATEGORIES, CATEGORY_LABELS } from "../scenarioLibrary";
import FilterSlider, { type FilterOption } from "./FilterSlider";

/** Level 1, the origin of a Scenario: who it comes from.
 *
 * "followup" is a slot without data behind it. A Folgegespräch continues an
 * earlier Session, which needs the cross-Session memory of F-23, and that is
 * not built. Rather than add a column nothing writes and nothing reads (the
 * mistake that got `scenario_type` removed), the option exists in the UI,
 * counts zero and says so. Once F-23 lands, `matchesFilter` gains one line. */
export type LibraryFilter = "all" | "standard" | "own" | "followup" | "tenant";

/** Level 2, the thematic category (ADR 0064). */
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
  followup: "Folgegespräch",
};

const BASE_ORIGINS = ["all", "standard", "own", "followup"] as const;

export interface LibraryItem {
  id: string;
  name: string;
  subtitle: string;
  origin: Origin;
  /** Shared with the company (own or a colleague's). */
  shared: boolean;
  /** F-03 call context, or null for an uncategorised Scenario (ADR 0064). */
  category: ScenarioCategory | null;
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
}

/** Whether an item passes the active origin filter. "tenant" = anything shared
 * with the company, the author's own shared Scenarios included. */
export function matchesFilter(item: LibraryItem, filter: LibraryFilter): boolean {
  if (filter === "all") return true;
  if (filter === "standard") return item.origin === "builtin";
  if (filter === "own") return item.origin === "own";
  // Nothing is a Folgegespräch yet; see the note on LibraryFilter.
  if (filter === "followup") return false;
  return item.shared;
}

/** Whether an item passes the active category filter. An uncategorised
 * Scenario matches only "all". There is no category it belongs to, and filing
 * it under one nobody chose would be a guess (ADR 0064). */
export function matchesCategory(item: LibraryItem, category: CategoryFilter): boolean {
  return category === "all" || item.category === category;
}

function badgeLabel(item: LibraryItem, tenantName: string | null): string {
  if (item.origin === "own") return item.shared ? "Individuell · geteilt" : "Individuell";
  if (item.origin === "tenant") return tenantName ?? "Unternehmen";
  return "Standard";
}

/**
 * The Scenario selection grid: two filter rows, a "new" button, badged cards,
 * and an edit affordance on the caller's own rows (ADR 0058 / 0060 / 0064).
 *
 * The rows are independent and combine. Level 1 says where a Scenario comes
 * from, level 2 says what kind of call it is. Both are the same component, so
 * they are the same size by construction.
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
}: LibraryPickerProps) {
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
      <div className="library-filters">
        <FilterSlider
          options={originOptions}
          value={filter}
          onChange={onFilter}
          label="Szenarien nach Herkunft filtern"
        />
        <FilterSlider
          options={categoryOptions}
          value={category}
          onChange={onCategory}
          label="Szenarien nach Kategorie filtern"
        />
      </div>

      <div className="library-toolbar">
        <button type="button" className="library-new-button" onClick={onNew}>
          {newLabel}
        </button>
      </div>

      {items.length === 0 && (
        <p className="library-empty">
          {filter === "followup"
            ? "Folgegespräche gibt es noch nicht."
            : "Zu dieser Auswahl gibt es kein Szenario."}
        </p>
      )}

      <div className="persona-grid">
        {items.map((item) => (
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
              <span className="card-subtitle">{item.subtitle}</span>
              <span
                className={
                  "card-badge card-badge-" +
                  (item.origin === "own" && item.shared ? "shared" : item.origin)
                }
              >
                {badgeLabel(item, tenantName)}
              </span>
            </button>
            {item.origin === "own" && (
              <button type="button" className="card-edit" onClick={() => onEdit(item.id)}>
                Bearbeiten
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
