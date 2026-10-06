import { useState } from "react";

import { deleteSession } from "../sessions";

/** Deleting one stored training (ADR 0066). The history's bin needs to know whether one is in flight. */
export function useSessionDeletion(sessionId: string | undefined, onDeleted: () => void) {
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);

  const remove = async () => {
    // The route param is optional.
    if (!sessionId) return;
    setDeleting(true);
    setFailed(false);
    try {
      await deleteSession(sessionId);
      onDeleted();
    } catch (e) {
      console.debug("[delete session] failed", e);
      setFailed(true);
      setDeleting(false);
    }
  };

  return { deleting, failed, remove };
}

/** Says what goes with the training, since deletion is final. */
export default function DeleteSessionPrompt({
  deleting,
  failed,
  onConfirm,
  onCancel,
}: {
  deleting: boolean;
  failed: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <>
      <p>
        <strong>Dieses Training löschen?</strong> Gesprächsprotokoll, Kennzahlen und
        Auswertung werden entfernt. Das lässt sich nicht rückgängig machen.
      </p>
      <div className="consent-confirm-actions">
        <button
          type="button"
          className="consent-button consent-button-danger"
          onClick={onConfirm}
          disabled={deleting}
        >
          {deleting ? "Wird gelöscht …" : "Endgültig löschen"}
        </button>
        <button
          type="button"
          className="consent-button consent-button-secondary"
          onClick={onCancel}
          disabled={deleting}
        >
          Abbrechen
        </button>
      </div>
      {failed && (
        <p className="consent-error">
          Das Training konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.
        </p>
      )}
    </>
  );
}
