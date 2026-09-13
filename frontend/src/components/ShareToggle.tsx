import type { Visibility } from "../scenarioLibrary";

interface ShareToggleProps {
  visibility: Visibility;
  onChange: (next: Visibility) => void;
  label: string;
  hint?: string;
}

/** The single "share with my company" toggle (R-58 / ADR 0060): the entire
 * sharing interaction. Applies immediately, independent of the editor's Save. */
export default function ShareToggle({ visibility, onChange, label, hint }: ShareToggleProps) {
  const shared = visibility === "tenant";
  return (
    <label className="share-toggle">
      <input
        type="checkbox"
        checked={shared}
        onChange={(e) => onChange(e.target.checked ? "tenant" : "private")}
      />
      <span>
        <span className="share-toggle-label">{label}</span>
        {hint && <span className="share-toggle-hint">{hint}</span>}
      </span>
    </label>
  );
}
