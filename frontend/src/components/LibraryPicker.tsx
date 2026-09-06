import type { Origin } from "../scenarioLibrary";

export type LibraryFilter = "all" | "standard" | "own" | "tenant";

/** Static labels; the "tenant" chip is labelled with the company name. */
const FILTER_LABELS: Record<Exclude<LibraryFilter, "tenant">, string> = {
  all: "Alle",
  standard: "Standard",
  own: "Individuell",
};

const BASE_FILTERS = ["all", "standard", "own"] as const;

export interface LibraryItem {
  id: string;
  name: string;
  subtitle: string;
  origin: Origin;
  /** Shared with the company (own or a colleague's). */
  shared: boolean;
}

interface LibraryPickerProps {
  items: LibraryItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: LibraryFilter;
  onFilter: (f: LibraryFilter) => void;
  /** Show the filter chips (worth it once the user has own/shared rows or a company). */
  showFilter: boolean;
  filterLabel: string;
  /** The caller's company name (ADR 0060); null = default tenant, no company
   * chip or badge. */
  tenantName: string | null;
  newLabel: string;
  onNew: () => void;
  onEdit: (id: string) => void;
}

/** Whether an item passes the active filter. "tenant" = anything shared with
 * the company, the author's own shared Scenarios included. */
export function matchesFilter(item: LibraryItem, filter: LibraryFilter): boolean {
  if (filter === "all") return true;
  if (filter === "standard") return item.origin === "builtin";
  if (filter === "own") return item.origin === "own";
  return item.shared;
}

function badgeLabel(item: LibraryItem, tenantName: string | null): string {
  if (item.origin === "own") return item.shared ? "Individuell · geteilt" : "Individuell";
  if (item.origin === "tenant") return tenantName ?? "Unternehmen";
  return "Standard";
}

/** The Scenario selection grid: filter chips (Alle / Standard / Individuell /
 * <Unternehmen>), a "new" button, badged cards, and an edit affordance on the
 * caller's own rows (ADR 0058 / 0060). */
export default function LibraryPicker({
  items,
  selectedId,
  onSelect,
  filter,
  onFilter,
  showFilter,
  filterLabel,
  tenantName,
  newLabel,
  onNew,
  onEdit,
}: LibraryPickerProps) {
  return (
    <>
      <div className="library-toolbar">
        {showFilter && (
          <div className="library-filter" role="group" aria-label={filterLabel}>
            {BASE_FILTERS.map((f) => (
              <button
                key={f}
                type="button"
                className={"library-filter-chip" + (filter === f ? " active" : "")}
                aria-pressed={filter === f}
                onClick={() => onFilter(f)}
              >
                {FILTER_LABELS[f]}
              </button>
            ))}
            {tenantName && (
              <button
                type="button"
                className={"library-filter-chip" + (filter === "tenant" ? " active" : "")}
                aria-pressed={filter === "tenant"}
                onClick={() => onFilter("tenant")}
              >
                {tenantName}
              </button>
            )}
          </div>
        )}
        <button type="button" className="library-new-button" onClick={onNew}>
          {newLabel}
        </button>
      </div>

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
