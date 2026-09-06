import { useState } from "react";

import { apiFetch } from "../api";
import type { RetentionState } from "../protocol";
import { formatDate } from "../utils/time";

/**
 * The automatic deletion after six months, and the switch that suspends it
 * (ADR 0067).
 *
 * The period is the default and the switch is the exception, which is why the
 * text leads with the date rather than with the control: the useful thing to
 * know is when your oldest training goes, not that a toggle exists.
 *
 * Switching it off is not confirmed. It destroys nothing, and a confirmation
 * on the harmless direction would make the harmful ones look equally routine.
 */
export default function RetentionSettings({
  retention,
  onChange,
}: {
  retention: RetentionState;
  onChange: (next: RetentionState) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  const months = Math.round(retention.retention_days / 30);

  const toggle = async () => {
    setSaving(true);
    setFailed(false);
    try {
      const next = await apiFetch<RetentionState>("/api/me/retention", {
        method: "POST",
        body: JSON.stringify({ auto_delete: !retention.auto_delete }),
      });
      onChange(next);
    } catch (e) {
      console.debug("[retention] failed", e);
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="retention">
      {retention.auto_delete ? (
        <p>
          Ihre Trainings werden {months} Monate nach dem Gespräch automatisch gelöscht.
          {retention.next_expiry_at && (
            <> Das nächste fällt am {formatDate(retention.next_expiry_at)} weg.</>
          )}
        </p>
      ) : (
        <p>
          Die automatische Löschung ist ausgesetzt. Ihre Trainings bleiben gespeichert, bis Sie
          sie selbst löschen oder die Einwilligung widerrufen.
        </p>
      )}

      {failed && (
        <p className="consent-error">
          Die Einstellung konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.
        </p>
      )}

      <button
        type="button"
        className="consent-button consent-button-secondary"
        onClick={() => void toggle()}
        disabled={saving}
      >
        {saving
          ? "Wird gespeichert …"
          : retention.auto_delete
            ? "Automatische Löschung aussetzen"
            : "Automatisch löschen lassen"}
      </button>
    </div>
  );
}
