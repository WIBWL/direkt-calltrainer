import { useState } from "react";

import type { FocusChoice, FocusState } from "../protocol";
import AppHeader from "./AppHeader";
import FocusGoalPicker, { toggleGoal } from "./FocusGoalPicker";
import FocusProfilePicker from "./FocusProfilePicker";

/** Asked once (F-62, ADR 0076); picking nothing is offered as plainly as picking something. */
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
  const [profile, setProfile] = useState({
    role: focus.role,
    categories: focus.categories,
  });
  const [failed, setFailed] = useState(false);

  // Awaited, so a rejection is not lost. Role and call types go with either button.
  const submit = async (goals: string[]) => {
    setFailed(false);
    try {
      await onChoose({ goals, ...profile });
    } catch {
      setFailed(true);
    }
  };

  return (
    <div className="focus-onboarding">
      <AppHeader />

      <main className="focus-onboarding-main">
        <div className="setup-intro focus-onboarding-intro">
          <h1 id="focus-title">Worauf möchten Sie sich konzentrieren?</h1>

          <p className="setup-intro-description">
            Wählen Sie bis zu {focus.max_goals} Ziele. Auf diese Ziele schaut die Auswertung
            danach besonders genau.
          </p>
        </div>

        <section
          className="consent-dialog focus-dialog"
          aria-labelledby="focus-title"
        >
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
        </section>
      </main>

      {/* Outside the card, so the answers stay in reach while the list scrolls. */}
      <div className="focus-actions-bar">
        <div className="focus-actions-inner">
          <div className="focus-actions-copy">
            <div className="focus-tally">
              <span className="focus-count" aria-live="polite">
                {selected.length} von {focus.max_goals} Zielen ausgewählt.
                {selected.length >= focus.max_goals &&
                  " Wenn Sie tauschen möchten, wählen Sie zuerst ein Ziel ab."}
              </span>
            </div>

            <p className="focus-bar-note">
              Sie können Ihre Auswahl jederzeit im Profil ändern.
            </p>

            {failed && (
              <p className="consent-error">
                Ihre Auswahl konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.
              </p>
            )}
          </div>

          <div className="consent-actions">
            <button
              type="button"
              className="consent-button consent-button-secondary"
              onClick={() => void submit([])}
              disabled={saving}
            >
              Ohne Fokus fortfahren
            </button>

            <button
              type="button"
              className="consent-button consent-button-primary"
              onClick={() => void submit(selected)}
              disabled={saving || selected.length === 0}
            >
              {saving ? "Wird gespeichert …" : "Fokus übernehmen"}
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
