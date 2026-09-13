import type { FocusRole } from "../protocol";
import { CATEGORIES, CATEGORY_LABELS, type ScenarioCategory } from "../scenarioLibrary";

/**
 * The role and the kinds of call a User takes (F-62) — what the Scenario
 * suggestions are made from. Shared by the first-run dialog and the profile.
 *
 * Picking a role fills in the call types it usually means; they stay freely
 * adjustable, since a role is a guess about someone's work and they know better.
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
