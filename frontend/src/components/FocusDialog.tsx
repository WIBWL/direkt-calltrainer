import { useState } from "react";

import type { FocusChoice, FocusState } from "../protocol";
import FocusGoalPicker, { toggleGoal } from "./FocusGoalPicker";
import FocusProfilePicker from "./FocusProfilePicker";

/**
 * The training focus, asked once at the first start (F-62, ADR 0076).
 *
 * Two things have to be true of this screen or it does harm. Picking nothing
 * must be a real option, offered as plainly as picking something, which is why
 * the continue-without-a-focus button sits beside the save button and not below
 * it as an afterthought. And it must be clear that a focus *adds* emphasis
 * rather than switching the rest off, because a user who believes they are
 * turning ten goals off will pick none out of caution and the feature will
 * have cost them something.
 *
 * Fifteen cards is a lot for a first screen, which is why the captions carry
 * the meaning and the paragraphs sit behind an "i". Whoever wants to decide in
 * ten seconds can; whoever wants the detail has it. They sit two to a row for
 * the same reason, and the action bar stays put while the list scrolls: how
 * many are left and how to go on must not be a scroll away.
 *
 * Answerable later either way: the profile section changes the selection, and
 * the dialog says so, so nobody has to get this right on the first day.
 */
export default function FocusDialog({
  focus,
  onChoose,
  saving,
}: {
  focus: FocusState;
  onChoose: (choice: FocusChoice) => Promise<unknown>;
  saving: boolean;
}) {
  const [selected, setSelected] = useState<string[]>(focus.selected);
  const [profile, setProfile] = useState({ role: focus.role, categories: focus.categories });
  const [failed, setFailed] = useState(false);

  // Awaited rather than fired and forgotten: a rejected promise would go
  // unhandled and the dialog would sit there looking as if the click worked.
  // Role and call types go with either button: "no focus" is about the goals.
  const submit = async (goals: string[]) => {
    setFailed(false);
    try {
      await onChoose({ goals, ...profile });
    } catch {
      setFailed(true);
    }
  };

  return (
    <div
      className="consent-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="focus-title"
    >
      <div className="consent-dialog focus-dialog">
        <h1 id="focus-title">Worauf möchten Sie sich konzentrieren?</h1>

        <p>
          Wählen Sie bis zu {focus.max_goals} Ziele. Auf diese Ziele schaut die Auswertung
          danach besonders genau.
        </p>

        <p className="consent-highlight">
          <strong>Alles andere wird weiterhin trainiert.</strong> Ein Fokus gewichtet nur, er
          schaltet nichts ab.
        </p>

        <FocusProfilePicker
          roles={focus.roles}
          role={profile.role}
          categories={profile.categories}
          disabled={saving}
          onChange={setProfile}
        />

        <FocusGoalPicker
          goals={focus.goals}
          groups={focus.groups}
          selected={selected}
          max={focus.max_goals}
          disabled={saving}
          onToggle={(key) => setSelected((s) => toggleGoal(s, key, focus.max_goals))}
        />

        {/* Sticky, so the tally and both answers stay in view over a list
            that is taller than the viewport. */}
        <div className="focus-actions-bar">
          <div className="focus-tally">
            <span className="focus-slots" aria-hidden="true">
              {Array.from({ length: focus.max_goals }, (_, slot) => (
                <span
                  key={slot}
                  className={
                    "focus-slot" + (slot < selected.length ? " focus-slot-filled" : "")
                  }
                />
              ))}
            </span>
            <span className="focus-count" aria-live="polite">
              {selected.length} von {focus.max_goals} Zielen ausgewählt.
              {selected.length >= focus.max_goals &&
                " Wenn Sie tauschen möchten, wählen Sie zuerst ein Ziel ab."}
            </span>
          </div>

          {failed && (
            <p className="consent-error">
              Ihre Auswahl konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.
            </p>
          )}

          <div className="consent-actions">
            <button
              type="button"
              className="consent-button consent-button-primary"
              onClick={() => void submit(selected)}
              disabled={saving || selected.length === 0}
            >
              {saving ? "Wird gespeichert …" : "Fokus übernehmen"}
            </button>
            <button
              type="button"
              className="consent-button consent-button-secondary"
              onClick={() => void submit([])}
              disabled={saving}
            >
              Ohne Fokus fortfahren
            </button>
          </div>

          <p className="focus-bar-note">
            Sie können Ihre Auswahl jederzeit im Profil ändern.
          </p>
        </div>
      </div>
    </div>
  );
}
