import type { Origin, ScenarioCategory } from "../scenarioLibrary";
import { CATEGORIES, CATEGORY_LABELS } from "../scenarioLibrary";
import FilterSlider, { type FilterOption } from "./FilterSlider";

/** Level 1, the origin of a Scenario: who it comes from. "followUp" is the
 * worker-written Folgeszenario (ADR 0069), which is `origin: "own"` on the wire
 * but an option of its own here — "Individuell" means hand-authored. Not to be
 * confused with the level-2 CategoryFilter below. */
export type LibraryFilter = "all" | "standard" | "own" | "followUp" | "tenant";

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
};

const BASE_ORIGINS = ["all", "standard", "own", "followUp"] as const;

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
  /** Open the read-only info panel. Editing is reached from inside it
   * (ADR 0076), so the card carries no separate edit affordance. */
  onInfo: (id: string) => void;
}

/** Whether an item passes the active origin filter. "tenant" = anything shared
 * with the company, the author's own shared Scenarios included. */
export function matchesFilter(item: LibraryItem, filter: LibraryFilter): boolean {
  if (filter === "all") return true;
  if (filter === "standard") return item.origin === "builtin";
  if (filter === "followUp") return item.followUp;
  if (filter === "own") return item.origin === "own" && !item.followUp;
  return item.shared;
}

/** Whether an item passes the active category filter. An uncategorised
 * Scenario matches only "all". There is no category it belongs to, and filing
 * it under one nobody chose would be a guess (ADR 0072). */
export function matchesCategory(item: LibraryItem, category: CategoryFilter): boolean {
  return category === "all" || item.category === category;
}

/** The card's origin, which is also its badge class suffix. Not the level-2
 * category — the prop of that name is the thematic filter. */
function badgeClass(item: LibraryItem): string {
  if (item.followUp) return "follow-up";
  if (item.origin === "own") return item.shared ? "shared" : "own";
  return item.origin;
}

function badgeLabel(item: LibraryItem, tenantName: string | null): string {
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
  onInfo,
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
            : "Zu dieser Auswahl gibt es kein Szenario."}
        </p>
      )}

      <div className="persona-grid scenario-grid">
        {items.map((item) => (
          <div key={item.id} className="card-wrap">
            <button
              className={"persona-card" + (item.id === selectedId ? " selected" : "")}
              onClick={() => onSelect(item.id)}
              type="button"
              aria-pressed={item.id === selectedId}
            >
              <span className="choice-check" aria-hidden="true">
                {item.id === selectedId ? "✓" : ""}
              </span>
              <span className="persona-name">{item.name}</span>
              <span className="card-subtitle">{item.subtitle}</span>
              <span className={"card-badge card-badge-" + badgeClass(item)}>
                {badgeLabel(item, tenantName)}
              </span>
            </button>
            {/* Every Scenario is readable (ADR 0076), so the "i" is on every
                card — unlike the old "Bearbeiten", which was on the caller's
                own rows only and now lives inside the panel. */}
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
    </>
  );
}
