import { useState } from "react";

import type { FocusState } from "../protocol";
import FocusGoalPicker, { toggleGoal } from "./FocusGoalPicker";

/**
 * The training focus, asked once at the first start (F-62, ADR 0076).
 *
 * Two things have to be true of this screen or it does harm. Picking nothing
 * must be a real option, offered as plainly as picking something, which is why
 * "Ohne Fokus fortfahren" sits beside the save button and not below it as an
 * afterthought. And it must be clear that a focus *adds* emphasis rather than
 * switching the rest off, because a user who believes they are turning ten
 * goals off will pick none out of caution and the feature will have cost them
 * something.
 *
 * Fifteen cards is a lot for a first screen, which is why the captions carry
 * the meaning and the paragraphs sit behind an "i". Whoever wants to decide in
 * ten seconds can; whoever wants the detail has it.
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
  onChoose: (goals: string[]) => Promise<unknown>;
  saving: boolean;
}) {
  const [selected, setSelected] = useState<string[]>(focus.selected);
  const [failed, setFailed] = useState(false);

  // Awaited rather than fired and forgotten: a rejected promise would go
  // unhandled and the dialog would sit there looking as if the click worked.
  const submit = async (goals: string[]) => {
    setFailed(false);
    try {
      await onChoose(goals);
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

        <p className="consent-note">
          Sie können Ihre Auswahl jederzeit im Profil ändern.
        </p>

        <FocusGoalPicker
          goals={focus.goals}
          groups={focus.groups}
          selected={selected}
          max={focus.max_goals}
          disabled={saving}
          onToggle={(key) => setSelected((s) => toggleGoal(s, key, focus.max_goals))}
        />

        <p className="focus-count" aria-live="polite">
          {selected.length} von {focus.max_goals} Zielen ausgewählt.
          {selected.length >= focus.max_goals &&
            " Wenn Sie tauschen möchten, wählen Sie zuerst ein Ziel ab."}
        </p>

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
      </div>
    </div>
  );
}
