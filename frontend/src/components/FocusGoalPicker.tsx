import type { FocusGoal, FocusGroup } from "../protocol";
import InfoDetails from "./InfoDetails";

/** The same guard as the picker's `disabled` rule; the backend refuses one too many (ADR 0076). */
export function toggleGoal(selected: string[], key: string, max: number): string[] {
  if (selected.includes(key)) return selected.filter((k) => k !== key);
  return selected.length >= max ? selected : [...selected, key];
}

/** The catalogue as tickable cards (F-62, ADR 0076). At the limit only ticked cards stay enabled. */
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
  // Dropped here, so the numbering never skips.
  const shown = groups
    .map((group) => ({ group, inGroup: goals.filter((goal) => goal.group === group.key) }))
    .filter(({ inGroup }) => inGroup.length > 0);

  return (
    <div className="focus-groups">
      {shown.map(({ group, inGroup }, index) => {
        return (
          // A <section> heading alone does not label the checkboxes for a screen reader.
          <section
            className="focus-group"
            key={group.key}
            role="group"
            aria-labelledby={`focus-group-${group.key}`}
          >
            <h3 className="focus-group-title" id={`focus-group-${group.key}`}>
              {/* Numbers, not colours: in this palette a colour speaks about a value. */}
              <span className="focus-group-number" aria-hidden="true">{index + 1}</span>
              {group.name}
              {inGroup.some((goal) => selected.includes(goal.key)) && (
                <span className="focus-group-count">
                  · {inGroup.filter((goal) => selected.includes(goal.key)).length} gewählt
                </span>
              )}
            </h3>

            <ul className="focus-goal-list">
              {inGroup.map((goal) => {
                const position = selected.indexOf(goal.key);
                const checked = position !== -1;
                const locked = full && !checked;
                return (
                  <li key={goal.key}>
                    <div
                      className={
                        "focus-goal" +
                        (checked ? " focus-goal-selected" : "") +
                        (locked ? " focus-goal-locked" : "")
                      }
                    >
                      {/* `for`, not a wrapping label, or opening the "i" would toggle the box. */}
                      <input
                        type="checkbox"
                        id={`focus-goal-${goal.key}`}
                        className="focus-goal-input"
                        checked={checked}
                        disabled={disabled || locked}
                        onChange={() => onToggle(goal.key)}
                      />

                      <label
                        className="focus-goal-title"
                        htmlFor={`focus-goal-${goal.key}`}
                      >
                        {/* Clicking it ticks the box; hidden from the name. */}
                        <span className="choice-check focus-goal-check" aria-hidden="true">
                          {checked ? position + 1 : ""}
                        </span>
                        {goal.title}
                      </label>

                      <label
                        className="focus-goal-caption"
                        htmlFor={`focus-goal-${goal.key}`}
                      >
                        {goal.caption}
                      </label>

                      {/* Last, so the "i" stays bottom-right; icon only. */}
                      <InfoDetails label={`Was „${goal.title}“ bedeutet`} iconOnly>
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
