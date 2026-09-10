import { useState } from "react";

import { useFocusContext } from "../FocusContext";
import { CATEGORY_LABELS, type ScenarioCategory } from "../scenarioLibrary";
import FocusGoalPicker, { toggleGoal } from "./FocusGoalPicker";
import FocusProfilePicker from "./FocusProfilePicker";

/**
 * The training focus on the profile page: what is currently picked, and how to
 * change it (F-62, ADR 0076).
 *
 * Read-only until the user asks to edit. The section is passed on the way to
 * something else most of the time, and fifteen open checkboxes would make a
 * page about your account look like a form waiting to be filled in, while a
 * stray click on a checkbox that saved immediately would silently change what
 * the training emphasises.
 *
 * Editing therefore has an explicit Save, and Cancel restores what was there.
 * Neither direction is confirmed: unlike withdrawing consent, nothing here
 * destroys anything, and a confirmation on a harmless change makes the harmful
 * ones look equally routine.
 */
export default function FocusSettings() {
  const { focus, saving, choose } = useFocusContext();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [profile, setProfile] = useState<{
    role: string | null;
    categories: ScenarioCategory[];
  }>({ role: null, categories: [] });
  const [failed, setFailed] = useState(false);

  if (!focus) {
    return (
      <p className="muted">
        Ihre Fokusziele konnten nicht geladen werden. Bitte laden Sie die Seite neu.
      </p>
    );
  }

  const byKey = new Map(focus.goals.map((goal) => [goal.key, goal]));
  // A goal that has since been retired from the catalogue keeps its slot in the
  // stored selection but has no card to show; listing the key alone would say
  // nothing, so it is left out rather than rendered as a blank chip.
  const picked = focus.selected.map((key) => byKey.get(key)).filter((g) => g !== undefined);

  const start = () => {
    setFailed(false);
    setDraft(focus.selected);
    setProfile({ role: focus.role, categories: focus.categories });
    setEditing(true);
  };

  const save = async () => {
    setFailed(false);
    try {
      await choose({ goals: draft, ...profile });
      setEditing(false);
    } catch {
      setFailed(true);
    }
  };

  const roleName = focus.roles.find((r) => r.key === focus.role)?.name;

  if (!editing) {
    return (
      <>
        {(roleName || focus.categories.length > 0) && (
          <p>
            {roleName && <>Rolle: {roleName}. </>}
            {focus.categories.length > 0 &&
              <>Gespräche: {focus.categories.map((c) => CATEGORY_LABELS[c]).join(", ")}.</>}
          </p>
        )}

        {picked.length > 0 ? (
          <>
            <p>Auf diese Ziele schaut die Auswertung besonders genau:</p>
            <ul className="focus-summary">
              {picked.map((goal) => (
                <li key={goal.key}>{goal.title}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>
            Sie trainieren ohne besonderen Fokus. Alle Ziele werden gleich gewichtet.
          </p>
        )}

        <p className="muted">
          Ein Fokus gewichtet nur. Alles Übrige wird weiterhin trainiert.
        </p>

        <button type="button" className="consent-button consent-button-secondary" onClick={start}>
          Fokusziele ändern
        </button>
      </>
    );
  }

  return (
    <>
      <p>
        Wählen Sie bis zu {focus.max_goals} Ziele. Ohne Auswahl trainieren Sie ohne besonderen
        Fokus.
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
        selected={draft}
        max={focus.max_goals}
        disabled={saving}
        onToggle={(key) => setDraft((s) => toggleGoal(s, key, focus.max_goals))}
      />

      <p className="focus-count" aria-live="polite">
        {draft.length} von {focus.max_goals} Zielen ausgewählt.
        {draft.length >= focus.max_goals &&
          " Wenn Sie tauschen möchten, wählen Sie zuerst ein Ziel ab."}
      </p>

      {failed && (
        <p className="consent-error">
          Ihre Auswahl konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.
        </p>
      )}

      <div className="consent-confirm-actions">
        <button
          type="button"
          className="consent-button consent-button-primary"
          onClick={() => void save()}
          disabled={saving}
        >
          {saving ? "Wird gespeichert …" : "Auswahl speichern"}
        </button>
        <button
          type="button"
          className="cancel-button"
          onClick={() => setEditing(false)}
          disabled={saving}
        >
          Abbrechen
        </button>
      </div>
    </>
  );
}
