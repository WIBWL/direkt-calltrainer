import type { FocusRole } from "../protocol";
import { CATEGORIES, CATEGORY_LABELS, type ScenarioCategory } from "../scenarioLibrary";

/**
 * The User's role and kinds of call (F-62), from which Scenario suggestions are made.
 * Shared by the first-run screen and the profile. A role prefills its usual call types,
 * which stay freely adjustable.
 */
export default function FocusProfilePicker({
  roles,
  role,
  categories,
  onChange,
  disabled = false,
}: {
  roles: FocusRole[];
  role: string | null;
  categories: ScenarioCategory[];
  onChange: (next: { role: string | null; categories: ScenarioCategory[] }) => void;
  disabled?: boolean;
}) {
  const toggle = (category: ScenarioCategory) =>
    onChange({
      role,
      categories: categories.includes(category)
        ? categories.filter((c) => c !== category)
        // Vocabulary order, so the chips and the stored set read the same.
        : CATEGORIES.filter((c) => c === category || categories.includes(c)),
    });

  return (
    <section className="focus-profile">
      <h3 className="focus-group-title" id="focus-role-title">Ihre Rolle</h3>
      <div className="focus-chips" role="radiogroup" aria-labelledby="focus-role-title">
        {roles.map((option) => (
          <label
            key={option.key}
            className={"focus-chip" + (role === option.key ? " is-on" : "")}
          >
            <input
              type="radio"
              name="focus-role"
              checked={role === option.key}
              disabled={disabled}
              onChange={() => onChange({ role: option.key, categories: option.categories })}
            />
            {option.name}
          </label>
        ))}
      </div>

      <h3 className="focus-group-title" id="focus-calls-title">Welche Gespräche führen Sie?</h3>
      <div className="focus-chips" role="group" aria-labelledby="focus-calls-title">
        {CATEGORIES.map((category) => (
          <label
            key={category}
            className={"focus-chip" + (categories.includes(category) ? " is-on" : "")}
          >
            <input
              type="checkbox"
              checked={categories.includes(category)}
              disabled={disabled}
              onChange={() => toggle(category)}
            />
            {CATEGORY_LABELS[category]}
          </label>
        ))}
      </div>

      <p className="focus-profile-note">
        Daraus schlagen wir Ihnen passende Szenarien vor. Nach Ihrer Rolle vorbelegt,
        jederzeit änderbar.
      </p>
    </section>
  );
}
