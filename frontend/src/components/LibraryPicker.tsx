import type { Herkunft } from "../scenarioLibrary";

export type LibraryFilter = "alle" | "standard" | "eigen" | "unternehmen";

/** Static labels; the "unternehmen" chip is labelled with the company name. */
const FILTER_LABELS: Record<Exclude<LibraryFilter, "unternehmen">, string> = {
  alle: "Alle",
  standard: "Standard",
  eigen: "Eigene",
};

const BASE_FILTERS = ["alle", "standard", "eigen"] as const;

export interface LibraryItem {
  id: string;
  name: string;
  subtitle: string;
  herkunft: Herkunft;
  /** Shared with the company (own or a colleague's). */
  geteilt: boolean;
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
  companyLabel: string | null;
  newLabel: string;
  onNew: () => void;
  onEdit: (id: string) => void;
}

/** Whether an item passes the active filter. "unternehmen" = anything shared
 * with the company, the author's own shared Scenarios included. */
export function matchesFilter(item: LibraryItem, filter: LibraryFilter): boolean {
  if (filter === "alle") return true;
  if (filter === "standard") return item.herkunft === "vorlage";
  if (filter === "eigen") return item.herkunft === "eigen";
  return item.geteilt;
}

function badgeLabel(item: LibraryItem, companyLabel: string | null): string {
  if (item.herkunft === "eigen") return item.geteilt ? "Eigen · geteilt" : "Eigen";
  if (item.herkunft === "unternehmen") return companyLabel ?? "Unternehmen";
  return "Standard";
}

/** The Scenario selection grid: filter chips (Alle / Standard / Eigene /
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
  companyLabel,
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
            {companyLabel && (
              <button
                type="button"
                className={"library-filter-chip" + (filter === "unternehmen" ? " active" : "")}
                aria-pressed={filter === "unternehmen"}
                onClick={() => onFilter("unternehmen")}
              >
                {companyLabel}
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
              <span
                className={
                  "card-badge card-badge-" +
                  (item.herkunft === "eigen" && item.geteilt ? "geteilt" : item.herkunft)
                }
              >
                {badgeLabel(item, companyLabel)}
              </span>
            </button>
            {item.herkunft === "eigen" && (
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
