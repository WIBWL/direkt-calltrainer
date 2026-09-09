import type { FocusGoal, FocusGroup } from "../protocol";
import InfoDetails from "./InfoDetails";

/**
 * Ticking or unticking one goal, with the limit applied.
 *
 * Exported because both screens that show the picker need it, and because the
 * guard belongs next to the `disabled` rule in the picker below rather than
 * being restated in each of them: the two must agree on what the limit does,
 * and the backend refuses a sixth goal outright (ADR 0076).
 */
export function toggleGoal(selected: string[], key: string, max: number): string[] {
  if (selected.includes(key)) return selected.filter((k) => k !== key);
  return selected.length >= max ? selected : [...selected, key];
}

/**
 * The catalogue as a set of tickable cards, grouped by heading (F-62,
 * ADR 0076).
 *
 * One component for both places it appears — the first-run dialog and the
 * profile section. They differ in what surrounds them and in nothing else, and
 * two copies of a fifteen-card list would drift on the first catalogue change.
 *
 * The limit is enforced by disabling what cannot be picked rather than by
 * refusing the click afterwards: a checkbox that turns out not to have worked
 * is worse than one that says why it is unavailable. Already-ticked cards stay
 * enabled at the limit, so the way out is always to untick something.
 */
export default function FocusGoalPicker({
  goals,
  groups,
  selected,
  max,
  onToggle,
  disabled = false,
}: {
  goals: FocusGoal[];
  groups: FocusGroup[];
  selected: string[];
  max: number;
  onToggle: (key: string) => void;
  disabled?: boolean;
}) {
  const full = selected.length >= max;

  return (
    <div className="focus-groups">
      {groups.map((group) => {
        const inGroup = goals.filter((goal) => goal.group === group.key);
        // A group whose goals were all retired renders nothing rather than an
        // empty heading.
        if (inGroup.length === 0) return null;

        return (
          <section className="focus-group" key={group.key}>
            <h3 className="focus-group-title">{group.name}</h3>

            <ul className="focus-goal-list">
              {inGroup.map((goal) => {
                const checked = selected.includes(goal.key);
                return (
                  <li key={goal.key}>
                    <div className={`focus-goal${checked ? " focus-goal-selected" : ""}`}>
                      {/* The label carries the checkbox, so the whole title and
                          caption are the hit area. The "i" below stays outside
                          it — an interactive element nested in a label would
                          toggle the box when it is opened. */}
                      <label className="focus-goal-main">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled || (full && !checked)}
                          onChange={() => onToggle(goal.key)}
                        />
                        <span className="focus-goal-text">
                          <span className="focus-goal-title">{goal.title}</span>
                          <span className="focus-goal-caption">{goal.caption}</span>
                        </span>
                      </label>

                      <InfoDetails label="Was dieses Ziel bedeutet">
                        <p>{goal.info}</p>
                      </InfoDetails>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
