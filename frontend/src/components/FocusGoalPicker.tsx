import type { FocusGoal, FocusGroup } from "../protocol";
import InfoDetails from "./InfoDetails";

/**
 * Ticking or unticking one goal, with the limit applied. Exported so both screens share
 * the guard that matches the picker's `disabled` rule; the backend refuses a sixth goal
 * outright (ADR 0076).
 */
export function toggleGoal(selected: string[], key: string, max: number): string[] {
  if (selected.includes(key)) return selected.filter((k) => k !== key);
  return selected.length >= max ? selected : [...selected, key];
}

/**
 * The catalogue as tickable cards by group (F-62, ADR 0076), shared by the first-run
 * screen and the profile; the circle shows each pick's position. At the limit unpicked
 * cards are disabled, ticked ones stay enabled so the way out is to untick one.
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
  // A group whose goals were all retired is dropped here rather than returning
  // null below, so the numbering never skips a step.
  const shown = groups
    .map((group) => ({ group, inGroup: goals.filter((goal) => goal.group === group.key) }))
    .filter(({ inGroup }) => inGroup.length > 0);

  return (
    <div className="focus-groups">
      {shown.map(({ group, inGroup }, index) => {
        return (
          // role/aria-labelledby, because a <section> with a heading does not
          // tie the checkboxes inside it to that heading for a screen reader.
          <section
            className="focus-group"
            key={group.key}
            role="group"
            aria-labelledby={`focus-group-${group.key}`}
          >
            <h3 className="focus-group-title" id={`focus-group-${group.key}`}>
              {/* Numbered rather than colour-coded: in this palette a colour
                  says something about a value, and a group means nothing. */}
              <span className="focus-group-number" aria-hidden="true">{index + 1}</span>
              {group.name}
              {/* Where this group's picks sit, without scanning for ticks. */}
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
                      {/* `for`, not a wrapping label: that keeps the "i" a
                          sibling of the text. Inside a label it would toggle
                          the box whenever it was opened. Two labels on one
                          input are valid, so title and caption both stay part
                          of the hit area. */}
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
                        {/* In the label so that clicking it ticks the box;
                            hidden, so its number stays out of the name. */}
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

                      {/* Last in the card so the "i" stays pinned to the bottom-right
                      corner. The explanation itself opens as an overlay and does
                      not change the grid row height. Icon only: the same label on
                      every card is noise, and naming the goal makes it a better
                      one when read out. */}
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
