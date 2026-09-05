import type { Sichtbarkeit } from "../scenarioLibrary";

interface ShareToggleProps {
  sichtbarkeit: Sichtbarkeit;
  onChange: (next: Sichtbarkeit) => void;
  label: string;
  hint?: string;
}

/** The single "share with my company" toggle (R-58 / ADR 0060): the entire
 * sharing interaction. Applies immediately, independent of the editor's Save. */
export default function ShareToggle({ sichtbarkeit, onChange, label, hint }: ShareToggleProps) {
  const shared = sichtbarkeit === "unternehmen";
  return (
    <label className="share-toggle">
      <input
        type="checkbox"
        checked={shared}
        onChange={(e) => onChange(e.target.checked ? "unternehmen" : "privat")}
      />
      <span>
        <span className="share-toggle-label">{label}</span>
        {hint && <span className="share-toggle-hint">{hint}</span>}
      </span>
    </label>
  );
}
