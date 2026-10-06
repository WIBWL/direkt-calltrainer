import { useState, type ReactNode } from "react";

import { apiFetch } from "../api";
import type { RetentionState } from "../protocol";
import { formatDate } from "../utils/time";

/** The six-month deletion and its off switch (ADR 0067). Switching off is not
 * confirmed: confirming the harmless direction makes the harmful ones look routine. */
export default function RetentionSettings({
  retention,
  onChange,
  children,
}: {
  retention: RetentionState;
  onChange: (next: RetentionState) => void;
  children?: ReactNode;
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

      <div className="retention-actions">
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

        {children}
      </div>
    </div>
  );
}
